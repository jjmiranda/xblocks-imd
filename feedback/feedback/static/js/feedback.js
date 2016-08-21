function FeedbackXBlock(runtime, element) {

    var Columns = {
        Username: 0,
        Name: 1,
        Cohort: 2,
        InstructorsComments: 3,
        FeedbackFile: 4,
        FeedbackVideo: 5,
        Published: 6,
        Email: 7
    };

    function xblock($, _) {
        var sgaXDMEl = $(element).find('#feedback-easyxdm-content')[0];
        var kvCreator = new KVCreator(sgaXDMEl, '91', 'xblock:feedback', 'IMD edX');

        var template = _.template($(element).find("#student-view-tmpl").text());
        var studentDownloadFeedbackFileUrl = runtime.handlerUrl(element, 'student_download_feedback_file');

        var feedbackTemplate;
        var getFeedbackDataUrl = runtime.handlerUrl(element, 'get_feedback_data');
        var feedbackFileDownloadUrl = runtime.handlerUrl(element, 'feedback_file_download');
        var updateFeedbackTextUrl = runtime.handlerUrl(element, 'update_feedback_text');
        var feedbackFileUploadUrl = runtime.handlerUrl(element, 'feedback_file_upload');
        var staffDownloadFeedbackFileUrl = runtime.handlerUrl(element, 'staff_download_feedback_file');
        var addFeedbackVideoUrl = runtime.handlerUrl(element, 'add_feedback_video');
        var removeFeedbackVideoUrl = runtime.handlerUrl(element, 'remove_feedback_video');
        var fetchFeedbackVideoUrlsUrl = runtime.handlerUrl(element, 'fetch_feedback_video_urls');
        var publishFeedbackUrl = runtime.handlerUrl(element, 'publish_feedback');

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
            state.feedbackFileUrl = studentDownloadFeedbackFileUrl;
            state.feedbackFileIsPDF = state.feedback_mimetype && state.feedback_mimetype.toLowerCase() == 'application/pdf';
            // For PDF display we don't want the file as an attachment
            state.feedbackFileInlineURL  = studentDownloadFeedbackFileUrl + '?as_attachment=0';

            // Render template
            var content = $(element).find('#student-view-content').html(template(state));

            if (state.feedback_published && state.feedback_video) {
                updateUserFeedbackVideo(state.feedback_video);
            }
        }

        function updateUserFeedbackVideo(feedbackVideo) {
            var videoEl = $(element).find('#user-feedback-video');
            var playVideoError = $(element).find('#student-view-content .play-video-error');
            playVideoError.hide();

            loadVideoPlayer(feedbackVideo, videoEl, function() {
                playVideoError.text('The video is not available yet. Please try again later.');
                playVideoError.show();
            });
        }

        function pauseUserFeedbackVideo() {
            var videoEl = $(element).find('#user-feedback-video');
            if (videoEl[0]) {
                videojs(videoEl[0]).pause();
            }
        }

        function renderFeedbackUI(data) {

            function columnIndexFromColumnId(columnId) {
                var columnOrder = [Columns.Username, Columns.Name, Columns.InstructorsComments, Columns.FeedbackFile, Columns.FeedbackVideo, Columns.Published, Columns.Email];
                if (data.course_is_cohorted) {
                    columnOrder.splice(2, 0, Columns.Cohort);
                }
                return columnOrder.indexOf(columnId);
            }

            function initialiseTable() {
                var headersConfig = {};
                headersConfig[columnIndexFromColumnId(Columns.FeedbackFile)] = { sorter: false };

                $("#feedback-table").tablesorter({
                    headers: headersConfig,
                    sortList: lastSortList
                })
                .bind("sortEnd",function(sorter) {
                    lastSortList = sorter.target.config.sortList;
                });
                $("#feedback-table").trigger("update");
            }

            var searchTimeoutId = undefined;
            var cohorts = {};


            $(element).find('.staff-modal').on("imdLeanModal:close", function(e) {
                $(element).find('#feedback-info').empty();
            })

            if (data.display_name !== '') {
                $('.feedback-block .display_name').html(data.display_name);
            }

            data.truncated_feedback_text_size = 200;
            data.feedbackFileUrl = staffDownloadFeedbackFileUrl;

            $(element).find('#feedback-info')
                .html(feedbackTemplate(data))
                .data(data);

            data.student_feedback_list.map(function(student_feedback) {
                if (student_feedback.cohort_name) {
                    cohorts[student_feedback.cohort_name] = 1;
                }
                $(element).find('#feedback-info #row-' + student_feedback.module_id)
                    .data(student_feedback);
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

            $(element).find('.enter-comment')
                .imdLeanModal({closeButton: '.feedback-block #enter-comment-cancel'})
                .on('click', handleCommentEntry);

            $(element).find('#feedback-info .fileupload').each(function() {
                var row = $(this).parents("tr");
                var url = feedbackFileUploadUrl + "?module_id=" + row.data("module_id");
                var fileUpload = $(this).fileupload({
                    url: url,
                    pasteZone: null,
                    dropZone: null,
                    progressall: function(e, data) {
                        var percent = parseInt(data.loaded / data.total * 100, 10);
                        var do_upload = row.find('.fileupload-label').text('Uploading... ' + percent + '%');
                        do_upload.removeClass('fileupload-label-button');
                    },
                    done: function(e, data) {
                        // Add a time delay so user will notice upload finishing
                        // for small files
                        setTimeout(
                            function() { renderFeedbackUI(data.result); },
                            3000);
                    }
                });

                updateChangeEvent(fileUpload);
            });

            initialiseTable();

            $(element).find('.add-video-button')
                .imdLeanModal({closeButton: '.feedback-block #add-video-cancel', closeOnOverlayClick:false})
                .on('click', handleAddVideo);

            $(element).find('.play-video-button')
                .imdLeanModal({closeButton: '.feedback-block #play-video-done'})
                .on('click', handlePlayVideo);

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

            $(element).find('.remove-video-button').click(onRemoveVideoClicked);

            $(element).find('.publish-button').click(function() {
                var row = $(this).parents("tr");
                handlePublishFeedback(row);
            });

            $(element).find('.mail-icon').click(function() {
                var row = $(this).parents("tr");
                onEmailClicked(row.data('email'), data.email_subject, data.email_body);
            });

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

            function filterStudents(searchText) {
                var searchString = $(element).find('#input-username').val().toLowerCase();
                var tableNodes = $(element).find('#feedback-table tbody').children();
                var visibleNodeCount = tableNodes.length;
                var commentCount = 0;
                var fileCount = 0;
                var videoCount = 0;
                var publishedCount = 0;

                tableNodes.each(function (index) {
                    var assignment = $(this).data();
                    if ((searchString.length == 0 ||
                            (assignment.username.toLowerCase().indexOf(searchString) >= 0) ||
                            (assignment.fullname.toLowerCase().indexOf(searchString) >= 0)) &&
                        (searchCohortString.length == 0 ||
                            (assignment.cohort_name.toLowerCase().indexOf(searchCohortString) >= 0))) {
                        $(this).show();
                        commentCount += assignment.feedback_text ? 1 : 0;
                        fileCount += assignment.feedback_filename ? 1 : 0;
                        videoCount += assignment.feedback_video ? 1 : 0;
                        publishedCount += assignment.feedback_published ? 1 : 0;
                    }
                    else {
                        $(this).hide();
                        visibleNodeCount--;
                    }
                });

                var studentCountText = 'Showing ' + visibleNodeCount + ' of ' + data.student_feedback_list.length + ' students';
                $(element).find('#student-count').text(studentCountText);
                $(element).find('#comment-count').text(commentCount);
                $(element).find('#file-count').text(fileCount);
                $(element).find('#video-count').text(videoCount);
                $(element).find('#published-count').text(publishedCount);
            }
        }

        function handleCommentEntry() {
            var row = $(this).parents("tr");
            var commentsModal = $(element).find(".comments-modal");
            var commentInput = commentsModal.find('#comment-input');
            commentInput.height(102);
            commentInput.val(row.data('feedback_text'));

            function updateFeedbackText(feedbackText) {
                $.ajax({
                    type: "POST",
                    url: updateFeedbackTextUrl,
                    data: JSON.stringify({
                        "module_id": row.data('module_id'),
                        "feedback_text": feedbackText
                    }),
                    success: function(data) {
                        commentsModal.find('#enter-comment-cancel').click();
                        renderFeedbackUI(data);
                    }
                });
            }

            commentsModal.find('#enter-comment').off('click').on('click', function() {
                updateFeedbackText(commentInput.val());
            });
            commentsModal.find('#remove-comment').off('click').on('click', function() {
                updateFeedbackText('');
            });
        }

        ///////////////////////////////////////////////////////////////////////////

        function handleAddVideo() {
            var row = $(this).parents("tr");
            var addVideoModal = $(element).find('.add-video-modal');

            addVideoModal.off("imdLeanModal:close").on("imdLeanModal:close", function(e) {
                kvCreator.close();
            });

            kvCreator.open(onVideoCreated, row.data("module_id"));
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
                            errorDialog("#feedback-content", 'Play Video', 'The video does not appear to exist. Please check the video id you entered.');
                        }
                        else {
                            errorDialog("#feedback-content", 'Play Video', 'An error occurred on the server.');
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

            confirmDialog('#feedback-info', 'Delete Video', 'The video will be deleted. Are you sure?', 'Delete Video', function() {
                $.ajax({
                    type: "POST",
                    url: removeFeedbackVideoUrl,
                    data: JSON.stringify({
                        "module_id": moduleId
                    }),
                    success: renderFeedbackUI
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
                    renderFeedbackUI(data);
                },
                error: function(jqXHR, textStatus, errorThrown) {
                    if (jqXHR.status == 404) {
                        errorDialog("#feedback-info", 'Set Feedback Video', 'Video not found. Please check the video id you entered.');
                    }
                    else {
                        errorDialog("#feedback-info", 'Set Feedback Video', 'An error occurred on the server.');
                    }
                }
            });
        }

        function onVideoCreated(moduleId, videoId) {
            setFeedbackVideoId(moduleId, videoId)
            var cancelButton = $(element).find('.add-video-modal').find('#add-video-cancel');
            cancelButton.click();
        }

        ///////////////////////////////////////////////////////////////////////////

        function handlePublishFeedback(row) {
            var feedbackPublished = !row.data('feedback_published');
            $.ajax({
                type: "POST",
                url: publishFeedbackUrl,
                data: JSON.stringify({
                    "module_id": row.data('module_id'),
                    "feedback_published": feedbackPublished
                }),
                success: renderFeedbackUI
            });
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

        $(function ($) {
            var block = $(element).find('.feedback-block');
            var state = JSON.parse(block.attr('data-state'));

            render(state);

            var show_staff_ui = block.attr('data-show-staff-ui') == 'True';
            if (show_staff_ui) {
                if (state.course_is_cohorted) {
                    $(element).find('#search-cohort').show();
                }
                else {
                    $(element).find('#search-cohort').hide();
                }

                feedbackTemplate = _.template($(element).find('#feedback-tmpl').text());
                block.find('#feedback-button')
                    .imdLeanModal()
                    .on('click', function() {
                        $.ajax({
                            url: getFeedbackDataUrl,
                            success: function(data) {
                                lastSortList = [[0, 0]];
                                searchCohortString = '';
                                $(element).find('#input-username').val('');
                                pauseUserFeedbackVideo();
                                renderFeedbackUI(data);
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
    };

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
            dialogClass: 'feedback-error-modal',
            title: title,
            buttons: {
                'OK': function() {
                    $(this).dialog("close");
                    onOkFunc();
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
