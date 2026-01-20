import os
import requests
from django.http import Http404
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.utils import IntegrityError
from django.urls import reverse
from django.views.generic import FormView, TemplateView
from django.contrib import messages
from organizations.models import OrganizationUser

from bugbox3.samples.models import Sample, MultiSpecimenImage
from bugbox3.samples.constants import STITCHER_SAMPLE_TYPES
from bugbox3.samples.tasks import crop_panorama_segmentation
from bugbox3.libs.utilities import get_json_context, cast_utc_time
from .permissions import IS_RESEARCH, IS_ADMIN
from .forms import StitcherForm, StitcherDeleteForm
from .stitcher_api import (
    get_root_message,
    get_stitcher_stats,
    get_upload_file,
    patch_upload_file,
    delete_upload_file,
    STITCHER_URL,
    STITCHER_JS_URL,
    ERROR_MSG_KEY
)
from . import constants


class StitcherView(PermissionRequiredMixin, TemplateView):

    permission_required = IS_RESEARCH
    template_name = 'core/stitcher.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stitcher_url = STITCHER_JS_URL
        stats = get_stitcher_stats()
        if constants.STITCHER_STATS_LS_PROJECTS in stats.keys():
            ls_projects_choices = [(v[0], f'{v[0]} ({v[1]})')
                                   for v in stats[constants.STITCHER_STATS_LS_PROJECTS]]
        else:
            ls_projects_choices = [(None, None)]

        context.update({
            'stats': stats,
            'json_context': get_json_context({
                'STITCHER_URL': stitcher_url,
                'ls_projects_choices': ls_projects_choices,
            })
        })
        root_message = get_root_message()
        if ERROR_MSG_KEY in root_message:
            messages.error(self.request, root_message[ERROR_MSG_KEY])
        return context


class StitcherUpdateView(PermissionRequiredMixin, FormView):

    permission_required = IS_ADMIN

    form_class = StitcherForm
    template_name = 'core/stitcher_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        orgs = OrganizationUser.objects.filter(
            user=self.request.user).values_list(
                'organization_id', flat=True)
        if not orgs:
            raise Http404
        guid = self.kwargs[constants.STITCHER_GUID]
        self.guid = guid
        self.data = get_upload_file(guid)
        self.stitcher_url = STITCHER_URL
        self.stitcher_js_url = STITCHER_JS_URL
        self.panorama_name = ''
        self.img_src = ''
        self.thumbnail_src = None
        self.label_src = f'/static/{self.guid}/{constants.STITCHER_LABEL_IMG}'
        self.nota_sample = None
        if constants.STITCHER_PANORAMA_PATH in self.data.keys():
            if self.data[constants.STITCHER_PANORAMA_PATH]:
                self.img_src = self.data[constants.STITCHER_PANORAMA_PATH].replace('/media/', '/static/')
                if self.data[constants.STITCHER_PANORAMA_THUMBNAIL_PATH]:
                    self.thumbnail_src = f'{self.stitcher_js_url}{self.data[constants.STITCHER_PANORAMA_THUMBNAIL_PATH].replace('/media/', '/static/')}'
                self.panorama_name = os.path.basename(self.data[constants.STITCHER_PANORAMA_PATH])
        if constants.STITCHER_NOTA_SAMPLE in self.data.keys():
            self.nota_sample = self.data[constants.STITCHER_NOTA_SAMPLE]

        return kwargs

    def get_context_data(self, **kwargs):
        context = super(StitcherUpdateView, self).get_context_data(**kwargs)
        orgs = OrganizationUser.objects.filter(
            user=self.request.user).values_list(
                'organization_id', flat=True)
        if not orgs:
            raise Http404
        disable_stitching = True
        disable_crop_save = True
        disable_delete = False
        dir_name = None
        potential_samples = []

        for v in constants.STITCHER_TIMEFIELDS:
            if v in self.data.keys():
                if self.data[v]:
                    self.data[v] = cast_utc_time(self.data[v])
        # check for required files
        if all([v in self.data.keys() for v in constants.STITCHER_FORM_REQUIRED_KEYS]):

            disable_stitching = False if self.data[constants.STITCHER_APPROVED] is None else True
            disable_delete = True if self.data[constants.STITCHER_APPROVED] else False
            # find samples in bugbox
            dir_name = self.data[constants.STITCHER_UPLOAD_DIR_NAME]
            vs = dir_name.split('_')
            if vs:
                samples_w_type = None
                samples_w_transect = None
                sample_ids = None
                samples = Sample.objects.user_access(self.request.user).filter(
                    site_visit__site__experiment__organization_id__in=orgs,
                    site_visit__site__site_name__icontains=vs[0]
                )
                if len(vs) >= 2:
                    if vs[1].lower() in STITCHER_SAMPLE_TYPES.keys():
                        sample_type = STITCHER_SAMPLE_TYPES[vs[1].lower()]
                        samples_w_type = samples.filter(sample_type=sample_type)
                    if len(vs) >= 3 and samples_w_type:
                        samples_w_transect = samples_w_type.filter(name_no__icontains=vs[2])
                if samples_w_transect:
                    sample_ids = samples_w_transect.values_list('id', flat=True)
                elif samples_w_type:
                    sample_ids = samples_w_type.values_list('id', flat=True)
                else:
                    sample_ids = samples.values_list('id', flat=True)
                if sample_ids:
                    potential_samples = [
                        (i, reverse('samples:sample', kwargs={'sample_id': i})) for i in sample_ids]
            if (self.data[constants.STITCHER_ANNOTATIONS_SEGMENT] \
                    or self.data[constants.STITCHER_ANNOTATIONS_UPDATED_AT_SEGMENT]) \
                    and self.data[constants.STITCHER_APPROVED] \
                    and self.data[constants.STITCHER_BUGBOX_SAMPLE_ID]:
                disable_crop_save = False
        first_potential_sample = potential_samples[0][0] if potential_samples else None
        context.update({
            'data': self.data,
            'panoarma_name': self.panorama_name,
            'img_src': f'{self.stitcher_js_url}{self.img_src}',
            'thumbnail_src': self.thumbnail_src,
            'label_src': f'{self.stitcher_js_url}{self.label_src}',
            'potential_samples': potential_samples,
            'nota_sample': self.nota_sample,
            'first_potential_sample': first_potential_sample,
            'form_action_url': reverse(
                'core:stitcher-form', kwargs={'guid': str(self.guid)}),
            'form_iden_crop_save': constants.STITCHER_FORM_CROPSAVE,
            'disable_crop_save': disable_crop_save,
            'json_context': get_json_context({
                constants.STITCHER_GUID: self.guid,
                'STITCHER_URL': self.stitcher_js_url,
                'disable_stitching': disable_stitching,
                'disable_delete': disable_delete,
                'stitcher_delete_url': reverse(
                    'core:stitcher-delete', kwargs={constants.STITCHER_GUID: str(self.guid)}),
                'first_potential_sample': first_potential_sample
            })
        })
        if ERROR_MSG_KEY in self.data.keys():
            messages.error(self.request, self.data[ERROR_MSG_KEY])
        return context

    def get_initial(self):
        initial = super().get_initial()
        data = get_upload_file(self.kwargs[constants.STITCHER_GUID])
        if constants.STITCHER_APPROVED in data.keys():
            initial[constants.STITCHER_APPROVED] = data[constants.STITCHER_APPROVED]
        if constants.STITCHER_UPLOAD_DIR_NAME in data.keys():
            initial[constants.STITCHER_UPLOAD_DIR_NAME] = data[constants.STITCHER_UPLOAD_DIR_NAME]
        if constants.STITCHER_BUGBOX_SAMPLE_ID in data.keys():
            initial[constants.STITCHER_BUGBOX_SAMPLE_ID] = data[constants.STITCHER_BUGBOX_SAMPLE_ID]
        if constants.STITCHER_NOTA_SAMPLE in data.keys():
            initial[constants.STITCHER_NOTA_SAMPLE] = data[constants.STITCHER_NOTA_SAMPLE]
        return initial

    def form_valid(self, form):
        formdata = form.cleaned_data
        if formdata[constants.STITCHER_FORM_IDENT] == constants.STITCHER_FORM_DEFAULT:
            if formdata[constants.STITCHER_APPROVED] == '':
                formdata[constants.STITCHER_APPROVED] = None
            v = patch_upload_file(self.guid, formdata)
            if constants.STITCHER_ERROR in v.keys():
                messages.error(
                    self.request, f'{v[constants.STITCHER_ERROR]}'
                )
            else:
                messages.success(
                    self.request, f'Succesfully updated {self.guid}'
                )
        elif formdata[constants.STITCHER_FORM_IDENT] == constants.STITCHER_FORM_CROPSAVE:
            try:
                this_sample = Sample.objects.user_access(self.request.user).get(
                    id=self.data[constants.STITCHER_BUGBOX_SAMPLE_ID])
            except Exception:
                raise Http404
            try:
                label_url = f'{self.stitcher_url}{self.label_src}'
                label_response = requests.get(label_url, stream=True)
                label_response.raise_for_status()
            except Exception:
                label_response = None
            try:
                img_url = f'{self.stitcher_url}{self.img_src}'
                response = requests.get(img_url, stream=True)
                response.raise_for_status()
                predictions_timestamp = cast_utc_time(self.data[constants.STITCHER_PREDICTIONS_TIMESTAMP_COCO])
                auat = self.data[constants.STITCHER_ANNOTATIONS_UPDATED_AT_SEGMENT]
                instance = MultiSpecimenImage(
                    sample=this_sample,
                    panorama_filename=self.panorama_name,
                    annotations_segment=self.data[constants.STITCHER_ANNOTATIONS_SEGMENT],
                    annotations_updated_at_segment=auat if auat else '',
                    predictions_coco=self.data[constants.STITCHER_PREDICTIONS_COCO],
                    predictions_timestamp_coco=predictions_timestamp,
                    upload_dir_name=self.data[constants.STITCHER_UPLOAD_DIR_NAME],
                    uuid=self.data[constants.STITCHER_GUID],
                    uploaded_by_user=self.request.user)
                img_name = f'{self.data[constants.STITCHER_UPLOAD_DIR_NAME]}.jpg'
                instance.image.save(img_name, ContentFile(response.content), save=False)
                if label_response:
                    label_img_name = f'{self.data[constants.STITCHER_UPLOAD_DIR_NAME]}_label.jpg'
                    instance.label_image.save(label_img_name, ContentFile(label_response.content), save=False)
                    # Save label image to Sample image field
                    if not this_sample.image:
                        sample_label_img_name = f'{self.data[constants.STITCHER_UPLOAD_DIR_NAME]}_label.jpg'
                        this_sample.image.save(sample_label_img_name, ContentFile(label_response.content), save=False)
                        this_sample.save()
                instance.save()
                transaction.on_commit(
                    lambda: crop_panorama_segmentation.delay((instance.id,), this_sample.id, self.request.user.id)
                )
                messages.success(
                    self.request, f'Succesfully initiated "Save to sample and crop" for {self.guid}')
                self.data[constants.STITCHER_BUGBOX_CROPED_SAVED] = str(instance.id)
                patch_upload_file(self.guid, self.data)
            except IntegrityError as e:
                messages.error(self.request, f'Error, possible duplicate image for this record, {e}')
            except Exception as e:
                messages.error(self.request, f'There was an error in "Save to sample". {e}')
        else:
            messages.error(self.request, 'There was an error in form submission.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('core:stitcher-form', kwargs={constants.STITCHER_GUID: self.guid})


class StitcherDeleteView(PermissionRequiredMixin, FormView):

    permission_required = IS_ADMIN

    form_class = StitcherDeleteForm
    template_name = 'core/confirm_delete_cris.html'

    def get_context_data(self, **kwargs):
        context = super(StitcherDeleteView, self).get_context_data(**kwargs)
        orgs = OrganizationUser.objects.filter(
            user=self.request.user).values_list(
                'organization_id', flat=True)
        if not orgs:
            raise Http404
        information = 'Are you sure you want to delete Shimsy upload with guid {0}'.format(
            self.kwargs[constants.STITCHER_GUID]
        )
        context.update({
            'information': information
        })
        return context

    def get_initial(self):
        initial = super().get_initial()
        guid = self.kwargs[constants.STITCHER_GUID]
        data = get_upload_file(guid)
        if constants.STITCHER_UPLOAD_DIR_NAME not in data.keys():
            raise Http404
        self.upload_dir_name = data[constants.STITCHER_UPLOAD_DIR_NAME]
        initial[constants.STITCHER_UPLOAD_DIR_NAME] = self.upload_dir_name
        initial[constants.STITCHER_GUID] = guid
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        response = delete_upload_file(data['guid'])
        if ERROR_MSG_KEY in response.keys():
            messages.error(self.request, response[ERROR_MSG_KEY])
        else:
            messages.warning(
                    self.request,
                    f'Succesfully deleted {self.upload_dir_name}'
                )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('core:stitcher')
