/* Javascript for StaffGradedAssignmentXBlock. */
function StaffGradedAssignmentXBlock(runtime, element) {

    var Columns = {
        Username: 0,
        Name: 1,
        Cohort: 2,
        File: 3,
        UploadedDate: 4,
        Grade: 5,
        InstructorsComments: 6,
        AnnotatedFile: 7,
        FeedbackVideo: 8,
        Email: 9
    };

    function xblock($, _) {
        var imdVideoRecorder = new IMDVideoRecorder('#sga-video-recorder', '90', 'xblock:edx-sga', 'IMD edX');

        var uploadUrl = runtime.handlerUrl(element, 'upload_assignment');
        var removeAssignmentUrl = runtime.handlerUrl(element, 'remove_assignment');
        var downloadUrl = runtime.handlerUrl(element, 'download_assignment');
        var studentDownloadUrl = runtime.handlerUrl(element, 'download_student_assignment');
        var annotatedUrl = runtime.handlerUrl(element, 'download_annotated');
        var getStaffGradingUrl = runtime.handlerUrl(
          element, 'get_staff_grading_data'
        );
        var staffDownloadUrl = runtime.handlerUrl(element, 'staff_download');
        var staffCreateDownloadAssignmentsZipUrl = runtime.handlerUrl(element, 'staff_create_download_assignments_zip');
        var staffDownloadAssignmentsUrl = runtime.handlerUrl(element, 'staff_download_assignments');
        var staffAnnotatedUrl = runtime.handlerUrl(
          element, 'staff_download_annotated'
        );
        var staffUploadUrl = runtime.handlerUrl(element, 'staff_upload_annotated');
        var enterGradeUrl = runtime.handlerUrl(element, 'enter_grade');
        var removeGradeUrl = runtime.handlerUrl(element, 'remove_grade');
        var addFeedbackVideoUrl = runtime.handlerUrl(element, 'add_feedback_video');
        var removeFeedbackVideoUrl = runtime.handlerUrl(element, 'remove_feedback_video');
        var fetchFeedbackVideoUrlsUrl = runtime.handlerUrl(element, 'fetch_feedback_video_urls');
        var template = _.template($(element).find("#sga-tmpl").text());
        var gradingTemplate;

        var lastSortList = [[0, 0]];
        var allCohortsOptionText = 'All Cohorts';
        var searchCohortString = '';

        var loadingOverlay = createLoadingOverlay();

        function createLoadingOverlay() {
            var overlay = $(document.createElement( "div" ));
            overlay.attr("id", 'loading-overlay');
            overlay.css({
                'position': 'fixed',
                'z-index': 10000000,
                'top': '0px',
                'left': '0px',
                'height': '100%',
                'width': '100%',
                'display': 'none',
                'text-align': 'center'
            });
            var spinner = $(document.createElement( "i" ));
            spinner.addClass('fa fa-spinner fa-spin foobar');
            spinner.css({
                'font-size': '40px',
                'position': 'relative',
                'top': 'calc(50% - 20px)'
            });
            overlay.append(spinner);
            $(element).append(overlay);
            return overlay;
        }

        $.ajaxSetup({
            beforeSend:function(){
                loadingOverlay.show();
            },
            complete:function(){
                loadingOverlay.hide();
            }
        });

        function render(state) {
            // Add download urls to template context
            state.downloadUrl = downloadUrl;
            state.studentDownloadUrl = studentDownloadUrl;
            state.annotatedUrl = annotatedUrl;
            state.error = state.error || false;

            // Render template
            var content = $(element).find('#sga-content').html(template(state));

            // Set up file upload
            var fileUpload = $(content).find('.fileupload').fileupload({
                url: uploadUrl,
                pasteZone: null,
                dropZone: null,
                add: function(e, data) {
                    var do_upload = $(content).find('.fileupload-label').html('');
                    do_upload.removeClass('fileupload-label-button');
                    $(content).find('p.error').html('');
                    do_upload.text('Uploading...');
                    var block = $(element).find(".sga-block");
                    var data_max_size = block.attr("data-max-size");
                    var size = data.files[0].size;
                    if (!_.isUndefined(size)) {
                        //if file size is larger max file size define in env(django)
                        if (size >= data_max_size) {
                            state.error = 'The file you are trying to upload is too large.';
                            render(state);
                            return;
                        }
                    }
                    data.submit();
                },
                progressall: function(e, data) {
                    var percent = parseInt(data.loaded / data.total * 100, 10);
                    $(content).find('.fileupload-label').text(
                        'Uploading... ' + percent + '%');
                },
                fail: function(e, data) {
                    /**
                     * Nginx and other sanely implemented servers return a
                     * "413 Request entity too large" status code if an
                     * upload exceeds its limit.  See the 'done' handler for
                     * the not sane way that Django handles the same thing.
                     */
                    if (data.jqXHR.status === 413) {
                        /* I guess we have no way of knowing what the limit is
                         * here, so no good way to inform the user of what the
                         * limit is.
                         */
                        state.error = 'The file you are trying to upload is too large.';
                    } else {
                        // Suitably vague
                        state.error = 'There was an error uploading your file.';

                        // Dump some information to the console to help someone
                        // debug.
                        console.log('There was an error with file upload.');
                        console.log('event: ', e);
                        console.log('data: ', data);
                    }
                    render(state);
                },
                done: function(e, data) {
                    /* When you try to upload a file that exceeds Django's size
                     * limit for file uploads, Django helpfully returns a 200 OK
                     * response with a JSON payload of the form:
                     *
                     *   {'success': '<error message'}
                     *
                     * Thanks Obama!
                     */
                    if (data.result.success !== undefined) {
                        // Actually, this is an error
                        state.error = data.result.success;
                        render(state);
                    } else {
                        // The happy path, no errors
                        render(data.result);
                    }
                }
            });

            updateChangeEvent(fileUpload);
            if (state.error) {
                $(content).find('p.error').focus();
            }

            $(element).find('.remove-assignment').click(function () {
                confirmDialog('#sga-content', 'Remove Assignment', 'Your uploaded assignment will be deleted. Are you sure?', 'Remove Assignment', function() {
                    $.ajax({
                        type: "POST",
                        url: removeAssignmentUrl,
                        data: JSON.stringify({}),
                        success: function(data) {
                            render(data);
                        }
                    });
                });
            });

            if (state.graded && state.feedback_video) {
                updateUserFeedbackVideo(state.feedback_video);
            }
        }

        function updateUserFeedbackVideo(feedbackVideo) {
            var videoEl = $(element).find('#sga-content').find('#user-feedback-video');
            var playVideoError = $(element).find('#sga-content').find('.grading .play-video-error');
            playVideoError.hide();

            loadVideoPlayer(feedbackVideo, videoEl, function() {
                playVideoError.text('The video is not available yet. Please try again later.');
                playVideoError.show();
            });
        }

        function pauseUserFeedbackVideo() {
            var videoEl = $(element).find('#sga-content').find('#user-feedback-video');
            if (videoEl[0]) {
                videojs(videoEl[0]).pause();
            }
        }

        function renderStaffGrading(data) {

            function columnIndexFromColumnId(columnId) {
                var columnOrder = [Columns.Username, Columns.Name, Columns.File, Columns.UploadedDate, Columns.Grade, Columns.InstructorsComments, Columns.AnnotatedFile, Columns.FeedbackVideo, Columns.Email];
                if (data.course_is_cohorted) {
                    columnOrder.splice(2, 0, Columns.Cohort);
                }
                return columnOrder.indexOf(columnId);
            }

            function initialiseTable() {

                function pad(num) {
                  var s = '00000' + num;
                  return s.substr(s.length-5);
                }

                $.tablesorter.addParser({
                  id: 'alphanum',
                  is: function(s) {
                    return false;
                  },
                  format: function(s) {
                    var str = s.replace(/(\d{1,2})/g, function(a){
                        return pad(a);
                    });

                    return str;
                  },
                  type: 'text'
                });

                var headersConfig = {};
                headersConfig[columnIndexFromColumnId(Columns.UploadedDate)] = { sorter: "alphanum" };
                headersConfig[columnIndexFromColumnId(Columns.AnnotatedFile)] = { sorter: false };
                headersConfig[columnIndexFromColumnId(Columns.Email)] = { sorter: false };

                $(element).find("#submissions").tablesorter({
                    headers: headersConfig,
                    sortList: lastSortList
                })
                .bind("sortEnd",function(sorter) {
                    lastSortList = sorter.target.config.sortList;
                });

                $(element).find("#submissions").trigger("update");
            }

            var searchTimeoutId = undefined;
            var cohorts = {};

            $(element).find('.staff-modal').on("imdLeanModal:close", function(e) {
                $(element).find('#grade-info').empty();
            })

            if (data.display_name !== '') {
                $('.sga-block .display_name').html(data.display_name);
            }

            // Add download urls to template context
            data.downloadUrl = staffDownloadUrl;
            data.annotatedUrl = staffAnnotatedUrl;
            data.truncated_comment_size_limit = 200;

            // Render template
            $(element).find('#grade-info')
                .html(gradingTemplate(data))
                .data(data);

            // Map data to table rows
            data.assignments.map(function(assignment) {
                if (assignment.cohort_name) {
                    cohorts[assignment.cohort_name] = 1;
                }
                $(element).find('#grade-info #row-' + assignment.module_id)
                    .data(assignment);
            });

            if (data.course_is_cohorted) {
                var cohortsSelect = $(element).find('.cohorts');
                cohortsSelect.empty();
                var cohortsSorted = _.keys(cohorts).sort();
                cohortsSorted.unshift(allCohortsOptionText);
                _.each(cohortsSorted, function(value) {
                    cohortsSelect.append($('<option>', {
                        value: value.toLowerCase(),
                        text : value
                    }));
                });
                cohortsSelect.val(searchCohortString == '' ? allCohortsOptionText.toLowerCase() : searchCohortString);
            }

            filterStudents();

            // Set up grade entry modal
            $(element).find('.enter-grade-button')
                .imdLeanModal({closeButton: '.sga-block #enter-grade-cancel'})
                .on('click', handleGradeEntry);

            $(element).find('.show-comments')
                .imdLeanModal({closeButton: '.sga-block #show-comments-cancel'})
                .on('click', handleShowComments);

            $(element).find('.add-video-button')
                .imdLeanModal({closeButton: '.sga-block #add-video-cancel', closeOnOverlayClick:false})
                .on('click', handleAddVideo);

            $(element).find('.play-video-button')
                .imdLeanModal({closeButton: '.sga-block #play-video-done'})
                .on('click', handlePlayVideo);

            $(element).find('.remove-video-button').click(onRemoveVideoClicked);

            $(element).find('.mail-icon').click(function() {
                var row = $(this).parents("tr");
                onEmailClicked(row.data('email'), data.email_subject, data.email_body);
            });

            // Set up annotated file upload
            $(element).find('#grade-info .fileupload').each(function() {
                var row = $(this).parents("tr");
                var url = staffUploadUrl + "?module_id=" + row.data("module_id");
                var fileUpload = $(this).fileupload({
                    url: url,
                    pasteZone: null,
                    dropZone: null,
                    progressall: function(e, data) {
                        var percent = parseInt(data.loaded / data.total * 100, 10);
                        var do_upload = row.find('.fileupload-label').text('Uploading... ' + percent + '%');
                        do_upload.removeClass('fileupload-label-button fileupload-label-button-grading');
                    },
                    done: function(e, data) {
                        // Add a time delay so user will notice upload finishing
                        // for small files
                        setTimeout(
                            function() { renderStaffGrading(data.result); },
                            3000);
                    }
                });

                updateChangeEvent(fileUpload);
            });

            initialiseTable();

            // search

            $(element).find('#input-username').keyup(function() {
                window.clearTimeout(searchTimeoutId);
                searchTimeoutId = window.setTimeout(function() {
                    filterStudents();
                }, 500);
            });

            $(element).find('.cohorts').change(function() {
                var selectedCohort = $(this).val();
                searchCohortString = (selectedCohort == allCohortsOptionText.toLowerCase()) ? '' : selectedCohort;
                filterStudents();
            });

            $(element).find('#search-clear-search').click(function() {
                $(element).find('#input-username').val('');
                filterStudents();
            });

            $(element).find('#search-clear-cohort-search').click(function() {
                $(element).find('.cohorts').val(allCohortsOptionText);
                $(element).find('.cohorts').trigger('change');
            });

            $(element).find('.enter-video-id-button').click(function() {
                var videoId = $(this).parent().find('#video-id-input').val();
                var row = $(this).parents("tr");
                var currentVideoId = '';
                if (row.data('feedback_video')) {
                    currentVideoId = row.data('feedback_video')['kulu_id'];
                }
                if (videoId && videoId != currentVideoId) {
                    setFeedbackVideoId(row.data("module_id"), videoId);
                }
            });

            function filterStudents(searchText) {
                var searchString = $(element).find('#input-username').val().toLowerCase();
                var tableNodes = $(element).find('#submissions tbody').children();
                var visibleNodeCount = tableNodes.length;
                var fileCount = 0;
                var gradedCount = 0;
                var videoCount = 0;
                var commentCount = 0;
                var annotatedCount = 0;
                var awaitingApprovalCount = 0;

                tableNodes.each(function (index) {
                    var assignment = $(this).data();
                    if ((searchString.length == 0 ||
                            (assignment.username.toLowerCase().indexOf(searchString) >= 0) ||
                            (assignment.fullname.toLowerCase().indexOf(searchString) >= 0)) &&
                        (searchCohortString.length == 0 ||
                            (assignment.cohort_name.toLowerCase().indexOf(searchCohortString) >= 0))) {
                        $(this).show();
                        fileCount += assignment.filename ? 1 : 0;
                        if (assignment.score) {
                            gradedCount++;
                            awaitingApprovalCount += !assignment.approved ? 1 : 0;
                        }
                        videoCount += assignment.feedback_video ? 1 : 0;
                        commentCount += assignment.comment ? 1 : 0;
                        annotatedCount += assignment.annotated ? 1 : 0;
                    }
                    else {
                        $(this).hide();
                        visibleNodeCount--;
                    }
                });

                var studentCountText = 'Showing ' + visibleNodeCount + ' of ' + data.assignments.length + ' students';
                $(element).find('#student-count').text(studentCountText);
                $(element).find('#file-count').text(fileCount);
                $(element).find('#graded-count').text(gradedCount);
                $(element).find('#awaiting-approval-count').text(awaitingApprovalCount);
                $(element).find('#video-count').text(videoCount);
                $(element).find('#comment-count').text(commentCount);
                $(element).find('#annotated-count').text(annotatedCount);
            }

            $(element).find('#csv-export').click(function () {
                confirmDialog('#grade-info', 'CSV Export', 'Export displayed rows to a .csv file?', 'Export', function() {
                    var csvData = submissionsCSVdata(data.course_is_cohorted, data.max_score);
                    var filename = "submissions.csv"
                    downloadCSV(csvData, filename);
                });
            });

            $(element).find('#assignments-export').click(function () {
                confirmDialog('#grade-info', 'Download Assigments', 'Download displayed assignments as a zip file?', 'Download', function() {
                    downloadAssignments();
                });
            });
        }

        function submissionsCSVdata(isCohorted, maxScore) {
            var tableNodes = $(element).find('#submissions tbody').children();
            var csvData = isCohorted ? 'Username,Name,Cohort,File Submitted?,Submitted Date,Grade,Comments\n' : 'Username,Name,File Submitted?,Submitted Date,Grade,Comments\n';
            tableNodes.each(function (index) {
                if ($(this).is(":visible")) {
                    var assignment = $(this).data();
                    function csvIfy(s) {
                        if (s) {
                            s = s.replace(/"/g, '""');
                        }
                        return '"' + s + '"';
                    }
                    // prevent Excel from misinterpreting e.g. as date/formula
                    function excelify(s) {
                        return ' ' + s;
                    }
                    csvData += csvIfy(assignment.username) + ',';
                    csvData += csvIfy(assignment.fullname) + ',';
                    if (isCohorted) {
                        csvData += csvIfy(assignment.cohort_name) + ',';
                    }
                    csvData += (assignment.filename ? 'yes' : 'no') + ',';
                    csvData += (assignment.timestamp_formatted ? csvIfy(assignment.timestamp_formatted) : '') + ',';
                    csvData += (assignment.score ? csvIfy(excelify(assignment.score + '/' + maxScore)) : 'ungraded') + ',';
                    csvData += csvIfy(excelify(assignment.comment)) + '\n';
                }
            });
            return csvData;
        }

        function downloadAssignments() {
            var tableNodes = $(element).find('#submissions tbody').children();
            var students = [];
            tableNodes.each(function (index) {
                if ($(this).is(":visible")) {
                    var assignment = $(this).data();
                    if (assignment.filename) {
                        students.push(assignment.student_id);
                    }
                }
            });

            $.ajax({
                type: "POST",
                url: staffCreateDownloadAssignmentsZipUrl,
                data: JSON.stringify({
                    "student_ids": students
                }),
                success: function(data) {
                    var filename = "dummy.zip"
                    var url = new URI(staffDownloadAssignmentsUrl).query({
                        id: data['id'],
                    });
                    downloadLink(url, filename);
                },
                error: function(jqXHR, textStatus, errorThrown) {
                }
            });
        }

        function downloadLink(url, filename) {
            var link = document.createElement("a");
            link.setAttribute("href", url);
            link.setAttribute("download", filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        function downloadCSV(csvData, filename) {
            var blob = new Blob([csvData], {type: 'text/csv;charset=utf-8;'});
            if (navigator.msSaveBlob) { // IE support
                navigator.msSaveBlob(blob, filename);
            } else {
                var url = URL.createObjectURL(blob);
                downloadLink(url, filename);
            }
        }

        /* Click event handler for "enter grade" */
        function handleGradeEntry() {
            var row = $(this).parents("tr");
            var form = $(element).find("#enter-grade-form");
            form.find('#student-name').text(row.data('fullname'));
            form.find('#module_id-input').val(row.data('module_id'));
            form.find('#submission_id-input').val(row.data('submission_id'));
            form.find('#student_id-input').val(row.data('student_id'));
            form.find('#grade-input').val(row.data('score'));
            form.find('#comment-input').val(row.data('comment'));
            form.off('submit').on('submit', function(event) {
                var max_score = row.parents('#grade-info').data('max_score');
                var score = Number(form.find('#grade-input').val());
                event.preventDefault();
                if (isNaN(score)) {
                    form.find('.error').html('<br/>Grade must be a number.');
                } else if (score !== parseInt(score)) {
                    form.find('.error').html('<br/>Grade must be an integer.');
                } else if (score < 0) {
                    form.find('.error').html('<br/>Grade must be positive.');
                } else if (score > max_score) {
                    form.find('.error').html('<br/>Maximum score is ' + max_score);
                } else {
                    // No errors
                    $.post(enterGradeUrl, form.serialize())
                        .success(function(data) {
                            form.find('#enter-grade-cancel').click();
                            renderStaffGrading(data);
                        });
                }
            });
            form.find('#remove-grade').off('click').click(function() {
                var url = removeGradeUrl + '?module_id=' +
                    row.data('module_id') + '&student_id=' +
                    row.data('student_id');
                $.get(url).success(function(data) {
                    form.find('#enter-grade-cancel').click();
                    renderStaffGrading(data);
                });
            });
        }

        function handleShowComments() {
            var row = $(this).parents("tr");
            $(element).find('#show-comments-text').html(row.data('comment_html'));
        }

        function onEmailClicked(to, subject, body) {
            function mailToUrl(to, subject, body) {
                var args = [];
                if (typeof subject !== 'undefined') {
                    args.push('subject=' + encodeURIComponent(subject));
                }
                if (typeof body !== 'undefined') {
                    args.push('body=' + encodeURIComponent(body))
                }
                var url = 'mailto:' + (to ? encodeURIComponent(to) : '');
                if (args.length > 0) {
                    url += '?' + args.join('&');
                }
                return url;
            }

            window.location.href = mailToUrl(to, subject, body);
        }

        function handleAddVideo() {
            var row = $(this).parents("tr");
            var addVideoModal = $(element).find('.add-video-modal');

            addVideoModal.off("imdLeanModal:close").on("imdLeanModal:close", function(e) {
                imdVideoRecorder.close();
            });

            imdVideoRecorder.open(onVideoCreated, row.data("module_id"));
        }

        function handlePlayVideo() {
            var row = $(this).parents("tr");
            var feedbackVideo = row.data('feedback_video');
            var playVideoModal = $(element).find('.play-video-modal');
            var videoEl = playVideoModal.find('#feedback-video');
            var playVideoError = playVideoModal.find('.play-video-error');

            playVideoError.hide();

            playVideoModal.off("imdLeanModal:close").on("imdLeanModal:close", function(e) {
                var player = videojs(videoEl[0]);
                player.reset();
            });

            function loadVideo(feedbackVideo) {
                loadVideoPlayer(feedbackVideo, videoEl, function() {
                    playVideoError.text('The video is not available yet. Please try again later.');
                    playVideoError.show();
                });

                $(element).find('#video-feedback-username').text(row.data('username'));
                $(element).find('#video-feedback-added-by').text(feedbackVideo['added_by'] || 'unknown');
                $(element).find('#video-feedback-added-on').text(feedbackVideo['added_on'] || 'unknown');
            }

            if (!feedbackVideo['mp4_url'] || !feedbackVideo['hls_url']) {
                $.ajax({
                    type: "POST",
                    url: fetchFeedbackVideoUrlsUrl,
                    data: JSON.stringify({
                        "module_id": row.data('module_id')
                    }),
                    success: function(data) {
                        if (data['mp4_url'] || data['hls_url']) {
                            feedbackVideo['mp4_url'] = data['mp4_url']
                            feedbackVideo['hls_url'] = data['hls_url']
                            row.data('feedback_video', feedbackVideo);
                        }
                        loadVideo(feedbackVideo);
                    },
                    error: function(jqXHR, textStatus, errorThrown) {
                        if (jqXHR.status == 404) {
                            errorDialog("#sga-content", 'Play Video', 'The video does not appear to exist. Please check the video id you entered.');
                        }
                        else {
                            errorDialog("#sga-content", 'Play Video', 'An error occurred on the server.');
                        }
                    }
                });
            }
            else {
                loadVideo(feedbackVideo);
            }
        }

        function loadVideoPlayer(feedbackVideo, videoEl, onFail) {
            var player = videojs(videoEl[0], {playbackRates:[0.75,1,1.25,1.5,1.75,2]});

            var mp4_url = feedbackVideo['mp4_url'];
            var mp4_mime_type = 'video/mp4'
            var hls_url = feedbackVideo['hls_url'];
            var hls_mime_type = 'application/vnd.apple.mpegURL'

            if ((mp4_url && player.canPlayType(mp4_mime_type)) ||
                (hls_url && player.canPlayType(hls_mime_type))) {

                player.src([
                    { type: mp4_mime_type, src: mp4_url },
                    { type: hls_mime_type, src: hls_url }
                ]);
                player.load();
            }
            else {
                player.reset();
                onFail();
            }
        }

        function onRemoveVideoClicked() {
            var row = $(this).parents("tr");
            var moduleId = row.data('module_id');

            confirmDialog('#grade-info', 'Delete Video', 'The video will be deleted. Are you sure?', 'Delete Video', function() {
                $.ajax({
                    type: "POST",
                    url: removeFeedbackVideoUrl,
                    data: JSON.stringify({
                        "module_id": moduleId
                    }),
                    success: renderStaffGrading
                });
            });
        }

        function setFeedbackVideoId(moduleId, videoId) {
            $.ajax({
                type: "POST",
                url: addFeedbackVideoUrl,
                data: JSON.stringify({
                    "module_id": moduleId,
                    "kulu_id": videoId
                }),
                success: function(data) {
                    renderStaffGrading(data);
                },
                error: function(jqXHR, textStatus, errorThrown) {
                    if (jqXHR.status == 404) {
                        errorDialog("#grade-info", 'Set Feedback Video', 'Video not found. Please check the video id you entered.');
                    }
                    else {
                        errorDialog("#grade-info", 'Set Feedback Video', 'An error occurred on the server.');
                    }
                }
            });
        }

        function onVideoCreated(moduleId, videoId) {
            setFeedbackVideoId(moduleId, videoId)
            var cancelButton = $(element).find('.add-video-modal').find('#add-video-cancel');
            cancelButton.click();
        }

        function updateChangeEvent(fileUploadObj) {
            fileUploadObj.off('change').on('change', function (e) {
                var that = $(this).data('blueimpFileupload'),
                    data = {
                        fileInput: $(e.target),
                        form: $(e.target.form)
                    };

                that._getFileInputFiles(data.fileInput).always(function (files) {
                    data.files = files;
                    if (that.options.replaceFileInput) {
                        that._replaceFileInput(data.fileInput);
                    }
                    that._onAdd(e, data);
                });
            });
        }

        $(function($) { // onLoad
            var block = $(element).find('.sga-block');
            var state = JSON.parse(block.attr('data-state'));

            render(state);

            var is_staff = block.attr('data-staff') == 'True';
            if (is_staff) {
                if (state.course_is_cohorted) {
                    $(element).find('#search-cohort').show();
                }
                else {
                    $(element).find('#search-cohort').hide();
                }

                gradingTemplate = _.template(
                    $(element).find('#sga-grading-tmpl').text());
                block.find('#grade-submissions-button')
                    .imdLeanModal()
                    .on('click', function() {
                        $.ajax({
                            url: getStaffGradingUrl,
                            success: function(data) {
                                lastSortList = [[0, 0]];
                                searchCohortString = '';
                                $(element).find('#input-username').val('');
                                pauseUserFeedbackVideo();
                                renderStaffGrading(data);
                            }
                        });
                    });
                block.find('#staff-debug-info-button')
                    .imdLeanModal()
                    .on('click', function() {
                        pauseUserFeedbackVideo();
                    });
            }
        });
    }

    function confirmDialog(appendTo, title, message, okButtonName, onOkFunc) {
        var dialogEl = $(element).find("#dialog-confirm");
        dialogEl.on( "dialogopen", function(event, ui) {
            $(this).text(message);
        });
        dialogEl.dialog({
            title: title,
            appendTo: appendTo,
            resizable: false,
            modal: true,
            dialogClass: 'dialog-confirm',
            buttons: [
                {
                    text: okButtonName,
                    click: function() {
                        $(this).dialog("close");
                        if (onOkFunc) {
                            onOkFunc();
                        }
                    }
                },
                {
                    text: 'Cancel',
                    click: function() {
                        $(this).dialog("close");
                    }
                }
            ]
        });
    }

    function errorDialog(appendTo, title, message, onOkFunc) {
        $("<div>" + message + "</div>").dialog({
            appendTo: appendTo,
            resizable: false,
            modal: true,
            dialogClass: 'sga-error-modal',
            title: title,
            buttons: {
                'OK': function() {
                    $(this).dialog("close");
                    if (onOkFunc) {
                        onOkFunc();
                    }
                }
            }
        });
    }

    function loadjs(url) {
        $('<script>')
            .attr('type', 'text/javascript')
            .attr('src', url)
            .appendTo(element);
    }

    if (require === undefined) {
        /**
         * The LMS does not use require.js (although it loads it...) and
         * does not already load jquery.fileupload.  (It looks like it uses
         * jquery.ajaxfileupload instead.  But our XBlock uses
         * jquery.fileupload.
         */
        loadjs('/static/js/vendor/jQuery-File-Upload/js/jquery.iframe-transport.js');
        loadjs('/static/js/vendor/jQuery-File-Upload/js/jquery.fileupload.js');
        xblock($, _);
    } else {
        /**
         * Studio, on the other hand, uses require.js and already knows about
         * jquery.fileupload.
         */
        require(['jquery', 'underscore', 'jquery.fileupload'], xblock);
    }
}
