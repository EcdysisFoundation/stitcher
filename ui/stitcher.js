import $ from 'jquery';
import DataTable from 'datatables.net-bs5';
import { Modal } from 'bootstrap';

let messageModalBody = document.getElementById('messageModal-body');
let messageModal = new Modal(document.getElementById('messageModal'), {
    keyboard: false
  })


function getUrl(dt_url, data_filters) {

    let url_args = '';
    let sep = '?';
    if (data_filters.ls_project) {
        // more sanitation required if view not on private network
        let cleaned_val = encodeURIComponent(data_filters.ls_project)
        url_args = `${sep}lsproject=${cleaned_val}`
        sep = '&'
    };
    // true false filters
    url_args += `${sep}unreviewed=${data_filters.unreviewed}`;
    if (sep == '?') {sep = '&'}; // there is at least one arg here
    url_args += `${sep}approved=${data_filters.approved}`;
    url_args += `${sep}disapproved=${data_filters.disapproved}`;
    url_args += `${sep}predictions=${data_filters.predictions}`;
    url_args += `${sep}annotations=${data_filters.annotations}`;
    url_args += `${sep}completed=${data_filters.completed}`;
    url_args += `${sep}not_completed=${data_filters.not_completed}`;
    url_args += `${sep}needs_linked=${data_filters.needs_linked}`;
    url_args += `${sep}sample_linked=${data_filters.sample_linked}`;
    url_args += `${sep}nota_sample=${data_filters.nota_sample}`;
    url_args += `${sep}has_duplicate=${data_filters.has_duplicate}`;

    return `${dt_url}/uploads${url_args}`
}

function getFilename(path) {
  if (path) {
    const lastSlashIndex = path.lastIndexOf('/');
    if (lastSlashIndex !== -1) {
      return path.substring(lastSlashIndex + 1);
    }
  }
  return '';
}

function getFormButton(data) {
    var buttonId = 'actionButton_' + data; // Assuming `row.id` is unique
    return `<button id="${buttonId}" class="btn btn-primary stitcher-form-button" data-row-id="${data}">-></button>`;
}

function getApproved(approved) {
    if (approved == null) {
        return approved
    }
    if (approved) {
        return 'Approved'
    }
    if (!approved) {
            return 'Retake or delete'
        }
    return approved
}

function sendZipFile(formData, api_url) {
    fetch(api_url, {
        method: 'POST',
        body: formData // The FormData object automatically sets the 'Content-Type' header to 'multipart/form-data'
    })
    .then(response => response.json()) // Parse the JSON response from the API
    .then(data => {
        messageModalBody.innerHTML = '<p>' + JSON.stringify(data) + '</p>';
        messageModal.show();
        $('#formFile').val('');
    })
    .catch(error => {
        messageModalBody.innerHTML = '<p>' + JSON.stringify(error) + '</p>';
        messageModal.show();
        $('#formFile').val('');
    });
}

function getSampleUrl(data, type, row) {
    if (row.bugbox_sample_id) {
        return `<a href="/samples/sample/${row.bugbox_sample_id}" target="_blank">${row.bugbox_sample_id}</a>`
    } else {
        if (row.nota_sample) {
            return '<i class="bi bi-ban"></i>'
        } else { return '' }
    }
}

function concatTen(data) {
    if (data) {
        return String(data).slice(0, 10)
    } else { return '' }
}

function getSent(data, type, row) {
    if (row.bugbox_croped_saved) {
        return '<i class="bi bi-send-check-fill h4 text-success"></i>'
    } if (row.nota_sample) {
        return '<i class="bi bi-ban"></i>'
    } else { return '' }
}


$(function () {
    const json_context = JSON.parse(document.getElementById('json_context').textContent)
    let data_filters = {
        ls_project: '',
        needs_linked: false,
        sample_linked: false,
        nota_sample: false,
        unreviewed: false,
        approved: false,
        disapproved: false,
        predictions: false,
        annotations: false,
        not_completed: false,
        completed: false,
        has_duplicate: false
    }

    let $confidenceInput = $('<input type="number" step="0.1" id="formConfidence" class="form-control" value="0.6" max="0.9" min="0.1" required="true">')
    $('.confidence-input').append($confidenceInput)

    function getPanoramaSrc(data, type, row) {
        let filename = getFilename(data)
        if (filename) {
            let result = `<a href="${json_context.STITCHER_URL}`
            let s = String(data).replace('media', 'static')
            result += `${s}" target="_blank">${filename}</a>`;
            return result
        } else {
            return 'no panorama available'
        }
    };

    var stitcher_table = $('#stitcher-table').DataTable({
        layout: {
            top: 'info',
            topStart:{
            pageLength: {
                    menu: [ 10, 25, 50, 100 ]
                }
            },
            topEnd: 'search',
            bottomStart: 'info',
            bottomEnd: 'paging'
        },
        ordering: false,
        processing: true,
        serverSide: true,
        ajax: {
            url: getUrl(json_context.STITCHER_URL, data_filters),
            dataSrc: 'data'
        },
        language: {
            searchPlaceholder: "Search"
        },
        columns: [
            {
                data: 'upload_dir_name',
            },{
                data: 'guid',
                render: getFormButton
            },{
                data: 'panorama_path',
                render: getPanoramaSrc
            },{
                data: 'approved',
                render: getApproved
            },{
                data: '',
                render: getSampleUrl
            },{
                data: 'predictions_timestamp_coco',
                render: concatTen
            },{
                data: 'label_studio_project'
            },{
                data: 'annotations_updated_at_segment',
                render: concatTen
            },{
                data: '',
                render: getSent
            }
        ]
    })

    $('#stitcher-table', 'body').on('click', '.stitcher-form-button', function () {
        var guid = $(this).data('row-id');
        window.open(`/core/stitcher-form/${guid}`, '_blank');
        })


    $('#formFile').on('change', function() {
        if ($(this).val()) {
        $uploadButton.removeAttr('disabled');
        } else {
        $uploadButton.attr('disabled', 'disabled');
        }
    });

    let $uploadButton = $('<button class="btn btn-warning mb-3 mt-2 text-nowrap" type="button" disabled>Upload Zip File</button>')
    $('.upload-button').append($uploadButton)
    $uploadButton.on('click', function() {
        $(this).prop('disabled', true);
        const fileInput = $('#formFile')[0];
        const selectedFile = fileInput.files[0];
        const formData = new FormData();
        formData.append('file', selectedFile);
        const confidence = $confidenceInput[0].value
        formData.append('confidence_threshold', confidence)
        const params = `?confidence_threshold=${confidence}`
        sendZipFile(formData, json_context.STITCHER_URL + '/upload-zip-images/' + params)
    });

    // api_url filters
    let new_datatables_url = '';
    let $lsProjectPicker = $('<select placeholder="Filter by" aria-label="Filter by" id="approved-picker" class="form-select"></select>')
        $('.label-studio-picker').append($lsProjectPicker)
        $lsProjectPicker.append(`<option value="">` + 'LS Projects' + `</option>`)
        $lsProjectPicker.append(json_context.ls_projects_choices.map(value => `<option value="${value[0]}">${value[1]}</option>`))
        $lsProjectPicker.val('')
    $lsProjectPicker.on('change', () => {
        data_filters.ls_project = $lsProjectPicker.val()
        new_datatables_url = getUrl(json_context.STITCHER_URL, data_filters)
        stitcher_table.ajax.url( new_datatables_url ).load();
    })

    let unreviewed_check = '';
    if (data_filters.unreviewed) {
        unreviewed_check = 'checked';
    };
    let $unreviewedCheck = $(`<input class="form-check-input" type="checkbox" value="" id="unreviewedCheck" ${unreviewed_check}>`)
    $('.unreviewed-check').append($unreviewedCheck)
    $unreviewedCheck.on('change', () => {
        data_filters.unreviewed = $unreviewedCheck.prop("checked");
        new_datatables_url = getUrl(json_context.STITCHER_URL, data_filters);
        stitcher_table.ajax.url( new_datatables_url ).load();
    })

    let approved_check = '';
    if (data_filters.approved) {
        approved_check = 'checked';
    };
    let $approvedCheck = $(`<input class="form-check-input" type="checkbox" value="" id="approvedCheck" ${approved_check}>`)
    $('.approved-check').append($approvedCheck)
    $approvedCheck.on('change', () => {
        data_filters.approved = $approvedCheck.prop("checked");
        new_datatables_url = getUrl(json_context.STITCHER_URL, data_filters);
        stitcher_table.ajax.url( new_datatables_url ).load();
    })

    let disapprove_check = '';
    if (data_filters.disapprove) {
        disapprove_check = 'checked';
    };
    let $disapprovedCheck = $(`<input class="form-check-input" type="checkbox" value="" id="disapprovedCheck" ${disapprove_check}>`)
    $('.disapproved-check').append($disapprovedCheck)
    $disapprovedCheck.on('change', () => {
        data_filters.disapproved = $disapprovedCheck.prop("checked");
        new_datatables_url = getUrl(json_context.STITCHER_URL, data_filters);
        stitcher_table.ajax.url( new_datatables_url ).load();
    })

    let predictions_check = '';
    if (data_filters.predictions) {
        predictions_check = 'checked';
    };
    let $predictionsCheck = $(`<input class="form-check-input" type="checkbox" value="" id="predictionsCheck" ${predictions_check}>`)
    $('.predictions-check').append($predictionsCheck)
    $predictionsCheck.on('change', () => {
        data_filters.predictions = $predictionsCheck.prop("checked");
        new_datatables_url = getUrl(json_context.STITCHER_URL, data_filters);
        stitcher_table.ajax.url( new_datatables_url ).load();
    })

    let annotations_check = '';
    if (data_filters.annotations) {
        annotations_check = 'checked';
    };
    let $annotationsCheck = $(`<input class="form-check-input" type="checkbox" value="" id="annotationsCheck" ${annotations_check}>`)
    $('.annotations-check').append($annotationsCheck)
    $annotationsCheck.on('change', () => {
        data_filters.annotations = $annotationsCheck.prop("checked");
        new_datatables_url = getUrl(json_context.STITCHER_URL, data_filters);
        stitcher_table.ajax.url( new_datatables_url ).load();
    })

    let completed_check = '';
    if (data_filters.completed) {
        completed_check = 'checked';
    };
    let $completedCheck = $(`<input class="form-check-input" type="checkbox" value="" id="completedCheck" ${completed_check}>`)
    $('.completed-check').append($completedCheck)
    $completedCheck.on('change', () => {
        data_filters.completed = $completedCheck.prop("checked");
        new_datatables_url = getUrl(json_context.STITCHER_URL, data_filters);
        stitcher_table.ajax.url( new_datatables_url ).load();
    })

    let not_completed_check = '';
    if (data_filters.not_completed) {
        not_completed_check = 'checked';
    };
    let $notCompletedCheck = $(`<input class="form-check-input" type="checkbox" value="" id="notCompletedCheck" ${not_completed_check}>`)
    $('.not-completed-check').append($notCompletedCheck)
    $notCompletedCheck.on('change', () => {
        data_filters.not_completed = $notCompletedCheck.prop("checked");
        new_datatables_url = getUrl(json_context.STITCHER_URL, data_filters);
        stitcher_table.ajax.url( new_datatables_url ).load();
    })

    let needs_linked_check = '';
    if (data_filters.needs_linked) {
        needs_linked_check = 'checked';
    }
    let $needsLinkedCheck = $(`<input class="form-check-input" type="checkbox" value="" id="needsLinkedCheck" ${needs_linked_check}>`)
    $('.needs-linked-check').append($needsLinkedCheck)
    $needsLinkedCheck.on('change', () => {
        data_filters.needs_linked = $needsLinkedCheck.prop("checked");
        new_datatables_url = getUrl(json_context.STITCHER_URL, data_filters);
        stitcher_table.ajax.url( new_datatables_url ).load();
    })

    let sample_linked_check = '';
    if (data_filters.sample_linked) {
        sample_linked_check = 'checked';
    };
    let $sampleLinkedCheck = $(`<input class="form-check-input" type="checkbox" value="" id="sampleLinkedCheck" ${sample_linked_check}>`)
    $('.sample-linked-check').append($sampleLinkedCheck)
    $sampleLinkedCheck.on('change', () => {
        data_filters.sample_linked = $sampleLinkedCheck.prop("checked");
        new_datatables_url = getUrl(json_context.STITCHER_URL, data_filters);
        stitcher_table.ajax.url( new_datatables_url ).load();
    })

    let nota_sample_check = '';
    if (data_filters.nota_sample) {
        nota_sample_check = 'checked';
    };
    let $notaSampleCheck = $(`<input class="form-check-input" type="checkbox" value="" id="notaSampleCheck" ${nota_sample_check}>`)
    $('.nota-sample-check').append($notaSampleCheck)
    $notaSampleCheck.on('change', () => {
        data_filters.nota_sample = $notaSampleCheck.prop("checked");
        new_datatables_url = getUrl(json_context.STITCHER_URL, data_filters);
        stitcher_table.ajax.url( new_datatables_url ).load();
    })

    let has_duplicate_check = '';
    if (data_filters.has_duplicate) {
        has_duplicate_check = 'checked';
    };
    let $hasDuplicateCheck = $(`<input class="form-check-input" type="checkbox" value="" id="hasDuplicateCheck" ${has_duplicate_check}>`)
    $('.has-duplicate-check').append($hasDuplicateCheck)
    $hasDuplicateCheck.on('change', () => {
        data_filters.has_duplicate = $hasDuplicateCheck.prop("checked");
        new_datatables_url = getUrl(json_context.STITCHER_URL, data_filters);
        stitcher_table.ajax.url( new_datatables_url ).load();
    })

})
