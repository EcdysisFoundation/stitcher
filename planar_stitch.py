"""Stitch overlapping photographs of a flat subject.

The mapping from each source image into the mosaic is a single 2D affine, and
the disagreement of a correspondence pair

    A_i @ [p, 1]  -  A_j @ [q, 1]

is linear in those affine parameters. So instead of estimating a transform per
pair and chaining them through a spanning tree, every image is placed by one
least-squares solve over all pairwise correspondences at once. Placement error
is then spread across the mosaic rather than accumulating along a chain.

Usage:
    python planar_stitch.py <image_dir> -o panorama.jpg
"""

import argparse
import glob
import itertools
import os
import time
from collections import deque

import cv2 as cv
import numpy as np

RNG_SEED = 12345


# --------------------------------------------------------------- feature stage

def detect_features(paths, megapix, max_features):
    """SIFT keypoints per image, returned in full-resolution coordinates.

    Detection runs on a downscaled copy for speed, but 0.6 MP (the usual
    default) erases millimetre-scale detail, so 3 MP is the useful floor here.
    """
    sift = cv.SIFT_create(nfeatures=max_features)
    features, sizes = [], []

    for path in paths:
        image = cv.imread(path)
        if image is None:
            raise IOError(f"cannot read {path}")
        height, width = image.shape[:2]
        sizes.append((width, height))

        scale = min(1.0, np.sqrt(megapix * 1e6 / (width * height)))
        small = cv.resize(image, (int(round(width * scale)),
                                  int(round(height * scale))),
                          interpolation=cv.INTER_AREA)
        keypoints, descriptors = sift.detectAndCompute(
            cv.cvtColor(small, cv.COLOR_BGR2GRAY), None)

        if descriptors is None:
            features.append((np.zeros((0, 2), np.float32), None))
        else:
            points = np.float32([kp.pt for kp in keypoints]) / scale
            features.append((points, descriptors))

    return features, sizes


def stratified_subset(points_a, points_b, cap, grid=16):
    """Thin correspondences evenly over the frame.

    A single densely textured specimen can supply thousands of matches and
    outvote the rest of the overlap, which biases the fit toward that object.
    """
    if len(points_a) <= cap:
        return points_a, points_b

    low = points_a.min(axis=0)
    span = np.maximum(points_a.max(axis=0) - low, 1e-6)
    cell = np.floor((points_a - low) / span * (grid - 1e-9)).astype(int)
    key = cell[:, 0] * grid + cell[:, 1]

    order = np.argsort(key, kind="stable")
    sorted_key = key[order]
    per_cell = max(1, cap // max(len(np.unique(key)), 1))

    keep, start = [], 0
    while start < len(order):
        end = start
        while end < len(order) and sorted_key[end] == sorted_key[start]:
            end += 1
        keep.extend(order[start:start + per_cell])
        start = end

    keep = np.array(sorted(keep))
    if len(keep) > cap:
        keep = keep[(np.arange(cap) * (len(keep) / cap)).astype(int)]
    return points_a[keep], points_b[keep]


def build_pairs(features, ratio, ransac_px, min_inliers, min_inlier_ratio, cap):
    """Robust inlier correspondences for every overlapping pair.

    Unlike the OpenCV detail matchers these are kept as explicit point lists
    rather than collapsed into one transform, because the global solve needs
    the individual points.
    """
    matcher = cv.FlannBasedMatcher(dict(algorithm=1, trees=4), dict(checks=64))
    pairs = []

    for i, j in itertools.combinations(range(len(features)), 2):
        points_i, desc_i = features[i]
        points_j, desc_j = features[j]
        if desc_i is None or desc_j is None or min(len(desc_i), len(desc_j)) < 2:
            continue

        raw = matcher.knnMatch(desc_i, desc_j, k=2)
        good = [m for pair in raw if len(pair) == 2
                for m, n in [pair] if m.distance < ratio * n.distance]
        if len(good) < min_inliers:
            continue

        src = np.float32([points_i[m.queryIdx] for m in good])
        dst = np.float32([points_j[m.trainIdx] for m in good])
        _, inliers = cv.estimateAffine2D(
            src, dst, method=cv.RANSAC, ransacReprojThreshold=ransac_px,
            maxIters=10000, confidence=0.999, refineIters=20)
        if inliers is None:
            continue

        mask = inliers.ravel().astype(bool)
        if mask.sum() < min_inliers or mask.sum() / len(good) < min_inlier_ratio:
            continue

        a, b = stratified_subset(src[mask], dst[mask], cap)
        pairs.append((i, j, a.astype(np.float64), b.astype(np.float64)))

    return pairs


def largest_group(n_images, pairs):
    """Image indices reachable from each other through matched pairs."""
    adjacency = {k: set() for k in range(n_images)}
    for i, j, _, _ in pairs:
        adjacency[i].add(j)
        adjacency[j].add(i)

    seen, groups = set(), []
    for start in range(n_images):
        if start in seen:
            continue
        queue, group = deque([start]), []
        seen.add(start)
        while queue:
            node = queue.popleft()
            group.append(node)
            for nxt in adjacency[node] - seen:
                seen.add(nxt)
                queue.append(nxt)
        groups.append(sorted(group))

    return sorted(groups, key=len, reverse=True)[0] if groups else []


# ----------------------------------------------------------------- global solve

def apply_affine(affine, points):
    return points @ affine[:, :2].T + affine[:, 2]


def solve_affines(n_images, pairs, huber=8.0, iterations=10):
    """One 2D affine per image, from a single least-squares system.

    There are only 3 unknowns per image per axis, so the normal equations stay
    tiny (36x36 for twelve images) no matter how many correspondences are fed
    in. Reweighting a few times keeps surviving mismatches from dominating.
    """
    members = sorted({k for i, j, _, _ in pairs for k in (i, j)})

    weight_of = {k: 0.0 for k in members}
    for i, j, a, _ in pairs:
        weight_of[i] += len(a)
        weight_of[j] += len(a)
    anchor = max(members, key=lambda k: (weight_of[k], -k))

    # Solve in a centred, unit-ish frame; raw pixel coordinates are badly
    # conditioned for the normal equations.
    stack = np.vstack([p for _, _, a, b in pairs for p in (a, b)])
    centre = stack.mean(axis=0)
    spread = float(np.abs(stack - centre).mean()) or 1.0

    local = [(i, j, (a - centre) / spread, (b - centre) / spread)
             for i, j, a, b in pairs]
    weights = [np.ones(len(a)) for _, _, a, _ in local]

    free = np.array([3 * k + o for k in range(n_images) if k != anchor
                     for o in (0, 1, 2)])
    fixed = np.array([3 * anchor, 3 * anchor + 1, 3 * anchor + 2])

    affines = None
    for iteration in range(iterations):
        normal = np.zeros((3 * n_images, 3 * n_images))
        for (i, j, a, b), weight in zip(local, weights):
            design = np.column_stack(
                [a[:, 0], a[:, 1], np.ones(len(a)),
                 -b[:, 0], -b[:, 1], -np.ones(len(b))])
            columns = np.array([3 * i, 3 * i + 1, 3 * i + 2,
                                3 * j, 3 * j + 1, 3 * j + 2])
            normal[np.ix_(columns, columns)] += design.T @ (weight[:, None] * design)

        block = normal[np.ix_(free, free)]
        mixed = normal[np.ix_(free, fixed)]
        # Ridge term keeps images without usable matches from making it singular.
        block = block + 1e-9 * max(np.trace(block) / len(free), 1.0) * np.eye(len(free))

        solution_x = np.linalg.lstsq(block, -mixed @ [1.0, 0, 0], rcond=None)[0]
        solution_y = np.linalg.lstsq(block, -mixed @ [0, 1.0, 0], rcond=None)[0]

        affines = np.zeros((n_images, 2, 3))
        affines[anchor] = [[1.0, 0, 0], [0, 1.0, 0]]
        cursor = 0
        for k in range(n_images):
            if k == anchor:
                continue
            affines[k, 0] = solution_x[cursor:cursor + 3]
            affines[k, 1] = solution_y[cursor:cursor + 3]
            cursor += 3

        if iteration == iterations - 1:
            break
        limit = huber / spread
        weights = []
        for i, j, a, b in local:
            residual = np.linalg.norm(apply_affine(affines[i], a)
                                      - apply_affine(affines[j], b), axis=1)
            weights.append(np.where(residual <= limit, 1.0,
                                    limit / np.maximum(residual, 1e-12)))

    # Back to pixel coordinates, then rescale so the mosaic does not drift in size.
    out = np.zeros_like(affines)
    for k, affine in enumerate(affines):
        linear = affine[:, :2]
        out[k, :, :2] = linear
        out[k, :, 2] = spread * affine[:, 2] + centre - linear @ centre

    mean_det = float(np.mean([abs(np.linalg.det(out[k][:, :2])) for k in members]))
    if mean_det > 1e-12:
        for k in members:
            out[k] = out[k] / np.sqrt(mean_det)

    return out, members


def residual_stats(affines, pairs):
    errors = np.concatenate([
        np.linalg.norm(apply_affine(affines[i], a) - apply_affine(affines[j], b),
                       axis=1)
        for i, j, a, b in pairs])
    return {
        "n": len(errors),
        "rms": float(np.sqrt((errors ** 2).mean())),
        "median": float(np.median(errors)),
        "p95": float(np.percentile(errors, 95)),
        "max": float(errors.max()),
    }


# -------------------------------------------------------------------- compose

def place(sizes, affines, order):
    """Shift every transform so the mosaic starts at the origin."""
    def corners_of(size, affine):
        width, height = size
        box = np.array([[0, 0], [width, 0], [width, height], [0, height]], float)
        return apply_affine(affine, box)

    origin = np.vstack([corners_of(sizes[k], affines[k]) for k in order]).min(axis=0)

    placed = {}
    for k in order:
        shifted = affines[k].copy()
        shifted[:, 2] -= origin
        corners = corners_of(sizes[k], shifted)
        x0, y0 = np.floor(corners.min(axis=0)).astype(int)
        x1, y1 = np.ceil(corners.max(axis=0)).astype(int)
        local = shifted.copy()
        local[0, 2] -= x0
        local[1, 2] -= y0
        placed[k] = {"affine": local, "corner": (int(x0), int(y0)),
                     "size": (int(x1 - x0), int(y1 - y0))}
    return placed


def warp_tile(image, affine, size):
    warped = cv.warpAffine(image, affine, size, flags=cv.INTER_LINEAR,
                           borderMode=cv.BORDER_REFLECT)
    solid = np.full(image.shape[:2], 255, np.uint8)
    mask = cv.warpAffine(solid, affine, size, flags=cv.INTER_NEAREST,
                         borderMode=cv.BORDER_CONSTANT, borderValue=0)
    return warped, mask


def build_level(paths, placed, order, scale):
    """Downscale first, then warp.

    Warping from full resolution into a small canvas point-samples a large
    reduction and aliases badly, besides being much slower.
    """
    level = []
    for k in order:
        info = placed[k]
        width = max(1, int(round(info["size"][0] * scale)))
        height = max(1, int(round(info["size"][1] * scale)))

        source = cv.imread(paths[k])
        small = cv.resize(source, None, fx=scale, fy=scale,
                          interpolation=cv.INTER_AREA) if scale < 1.0 else source
        del source

        affine = info["affine"].copy()
        affine[:, 2] *= scale
        warped, mask = warp_tile(small, affine, (width, height))
        del small

        level.append({
            "image": warped, "mask": mask, "size": (width, height),
            "corner": (int(round(info["corner"][0] * scale)),
                       int(round(info["corner"][1] * scale))),
        })
    return level


def compose(paths, sizes, affines, order, seam_megapix, exposure_megapix,
            block_size, blend_strength):
    placed = place(sizes, affines, order)

    def level_scale(megapix):
        area = sum(placed[k]["size"][0] * placed[k]["size"][1] for k in order)
        return float(min(1.0, np.sqrt(megapix * 1e6 / max(area / len(order), 1))))

    seam_scale = level_scale(seam_megapix)
    seam_level = build_level(paths, placed, order, seam_scale)

    # Exposure gets its own coarser level: block compensators cost roughly the
    # cube of the block count, so reusing the seam level dominates the run.
    relative = min(1.0, level_scale(exposure_megapix) / seam_scale)
    exposure_level = [{
        "image": cv.resize(d["image"], None, fx=relative, fy=relative,
                           interpolation=cv.INTER_AREA),
        "mask": cv.resize(d["mask"], None, fx=relative, fy=relative,
                          interpolation=cv.INTER_NEAREST),
        "corner": (int(round(d["corner"][0] * relative)),
                   int(round(d["corner"][1] * relative))),
    } for d in seam_level] if relative < 1.0 else [dict(d) for d in seam_level]

    compensator = cv.detail_BlocksChannelsCompensator(block_size, block_size, 1)
    compensator.feed([d["corner"] for d in exposure_level],
                     [d["image"] for d in exposure_level],
                     [d["mask"] for d in exposure_level])
    del exposure_level

    # Seams are searched near 1 MP so they can route around specimens instead
    # of slicing them, which a 0.1 MP search cannot resolve.
    seam_masks = cv.detail_DpSeamFinder("COLOR_GRAD").find(
        [d["image"].astype(np.float32) for d in seam_level],
        [d["corner"] for d in seam_level],
        [d["mask"] for d in seam_level])
    seam_masks = [cv.UMat.get(m) if isinstance(m, cv.UMat) else m
                  for m in seam_masks]
    del seam_level

    corners = [placed[k]["corner"] for k in order]
    tile_sizes = [placed[k]["size"] for k in order]
    roi = cv.detail.resultRoi(corners=corners, sizes=tile_sizes)
    blend_width = np.sqrt(roi[2] * roi[3]) * blend_strength / 100

    blender = cv.detail_MultiBandBlender()
    blender.setNumBands(int(np.log(blend_width) / np.log(2.0) - 1.0))
    blender.prepare(roi)

    for position, k in enumerate(order):
        source = cv.imread(paths[k])
        warped, mask = warp_tile(source, placed[k]["affine"], placed[k]["size"])
        del source
        compensator.apply(position, placed[k]["corner"], warped, mask)

        seam_mask = cv.bitwise_and(
            cv.resize(cv.dilate(seam_masks[position], None),
                      (mask.shape[1], mask.shape[0]),
                      interpolation=cv.INTER_LINEAR_EXACT), mask)
        blender.feed(cv.UMat(warped.astype(np.int16)), seam_mask, corners[position])
        del warped, mask, seam_mask

    panorama, _ = blender.blend(None, None)
    return cv.convertScaleAbs(panorama)


# ------------------------------------------------------------------------ main

def stitch(paths, detect_megapix=3.0, max_features=20000, ratio=0.75,
           ransac_px=6.0, min_inliers=40, min_inlier_ratio=0.12,
           max_points_per_pair=1500, huber_px=8.0, iterations=10,
           seam_megapix=1.0, exposure_megapix=0.15, block_size=32,
           blend_strength=5, verbose=True):
    if len(paths) < 2:
        raise ValueError("need at least 2 images")

    cv.setRNGSeed(RNG_SEED)
    cv.ocl.setUseOpenCL(False)

    features, sizes = detect_features(paths, detect_megapix, max_features)
    pairs = build_pairs(features, ratio, ransac_px, min_inliers,
                        min_inlier_ratio, max_points_per_pair)
    if not pairs:
        raise RuntimeError("no image pair matched reliably")

    order = largest_group(len(paths), pairs)
    if len(order) < 2:
        raise RuntimeError("fewer than two images could be linked")
    dropped = sorted(set(range(len(paths))) - set(order))

    pairs = [p for p in pairs if p[0] in order and p[1] in order]
    affines, _ = solve_affines(len(paths), pairs, huber_px, iterations)
    stats = residual_stats(affines, pairs)

    if verbose:
        print(f"tiles      {len(order)}/{len(paths)}"
              + (f"  dropped {[os.path.basename(paths[k]) for k in dropped]}"
                 if dropped else ""))
        print(f"pairs      {len(pairs)}  correspondences {stats['n']}")
        print(f"alignment  rms {stats['rms']:.2f} px   median "
              f"{stats['median']:.2f}   p95 {stats['p95']:.2f}   "
              f"max {stats['max']:.1f}")

    panorama = compose(paths, sizes, affines, order, seam_megapix,
                       exposure_megapix, block_size, blend_strength)
    return panorama, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", help="directory of images, or a glob pattern")
    parser.add_argument("-o", "--output", default="panorama.jpg")
    parser.add_argument("--pattern", default="image_r*",
                        help="filename pattern when a directory is given")
    parser.add_argument("--detect-megapix", type=float, default=3.0)
    parser.add_argument("--seam-megapix", type=float, default=1.0)
    parser.add_argument("--blend-strength", type=int, default=5)
    parser.add_argument("--quality", type=int, default=95)
    args = parser.parse_args()

    target = (os.path.join(args.images, args.pattern)
              if os.path.isdir(args.images) else args.images)
    paths = sorted(glob.glob(target))
    if not paths:
        raise SystemExit(f"no images matched {target}")
    print(f"{len(paths)} images")

    start = time.time()
    panorama, _ = stitch(paths, detect_megapix=args.detect_megapix,
                         seam_megapix=args.seam_megapix,
                         blend_strength=args.blend_strength)
    cv.imwrite(args.output, panorama, [cv.IMWRITE_JPEG_QUALITY, args.quality])
    print(f"panorama   {panorama.shape[1]}x{panorama.shape[0]} -> {args.output}"
          f"   ({time.time() - start:.1f}s)")


if __name__ == "__main__":
    main()
