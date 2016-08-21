function IMDProfileXBlock(runtime, element) {

    function xblock($, _) {
        var template = _.template($(element).find("#student-view-tmpl").text());
        var allCohortsOptionText = 'All Cohorts';
        var searchCohortString = '';

        var loadingOverlay = createLoadingOverlay();

        function createLoadingOverlay() {
            var overlay = $(document.createElement( "div" ));
            overlay.attr("id", 'profile-xblock-loading-overlay');
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
            var searchTimeoutId = undefined;
            var cohorts = {};

            var content = $(element).find('#student-view-content').html(template(state));

            var studentProfilesEl = $(element).find('#student-profiles');
            studentProfilesEl.shapeshift({
                minColumns: 1,
                enableDrag: false,
                enableCrossDrop: false,
                autoHeight: true,
                maxHeight: 500,
                minHeight: 100,
                gutterX: 20,
                gutterY: 20,
                animationSpeed: 100
            });

            state.student_profile_list.map(function(student_profile) {
                if (student_profile.cohort_name) {
                    cohorts[student_profile.cohort_name] = 1;
                }
                studentProfilesEl.find('#id-' + student_profile.student_id)
                    .data(student_profile);
            });

            if (state.course_is_cohorted) {
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

            studentProfilesEl.find('.student-profile-clickable').click(function() {
                var profileData = $(this).parents('.student-profile').data();
                handleShowProfile(profileData.vip, profileData.email, profileData.image_url, state.profile_display);
            });

            studentProfilesEl.find('.mail-icon').click(function() {
                var profileData = $(this).parents('.student-profile').data();
                onEmailClicked(profileData.email, '', '');
            });

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
                var profileNodes = studentProfilesEl.children();
                var visibleNodeCount = profileNodes.length;

                if (searchString.length > 0 || searchCohortString.length > 0) {
                    profileNodes.each(function (index) {
                        var profileData = $(this).data();
                        if ((searchString.length == 0 ||
                                (profileData.username.toLowerCase().indexOf(searchString) >= 0) ||
                                (profileData.fullname.toLowerCase().indexOf(searchString) >= 0)) &&
                            (searchCohortString.length == 0 ||
                                (profileData.cohort_name.toLowerCase().indexOf(searchCohortString) >= 0))) {
                            $(this).show();
                        }
                        else {
                            $(this).hide();
                            visibleNodeCount--;
                        }
                    });
                }
                else {
                    profileNodes.show();
                }

                studentProfilesEl.trigger("ss-rearrange");

                var studentCountText = 'Showing ' + visibleNodeCount + ' of ' + state.student_profile_list.length + ' students';
                $(element).find('#student-count').text(studentCountText);
            }
        }

        function handleShowProfile(vip, email, imageUrl, profile_display) {
            if (vip) {
              $.ajax({
                  type: "GET",
                  url: "https://my.imd.org/api/profile/" + vip + "/get-profile",
                  success: function(studentProfile) {
                      showStudentProfileDialog(studentProfile, email, imageUrl, profile_display);
                  }
              });
            }
        }

        function showStudentProfileDialog(studentProfile, email, imageUrl, profile_display) {
            var dialogEl = $(element).find("#student-profile-dialog");
            dialogEl.on( "dialogopen", function(event, ui) {
                var template = _.template($(element).find("#student-profile-dialog-tmpl").text());
                var context = {
                    profile: studentProfile,
                    image_url: imageUrl,
                    email: email,
                    profile_display: profile_display
                };
                var content = $(element).find('#student-profile-dialog-content').html(template(context));
                content.find('.mail-icon').click(function() {
                    onEmailClicked(email, '', '');
                });
            });
            var appendTo = '.profile-block';
            var fullName = studentProfile.FirstName + ' ' + studentProfile.LastName;
            var title = studentProfile.FirstName ? fullName : 'Student Profile';
            dialogEl.dialog({
                width: 600,
                title: title,
                appendTo: appendTo,
                resizable: false,
                modal: true,
                dialogClass: 'student-profile-dialog',
                buttons: [
                    {
                        text: 'OK',
                        click: function() {
                            $(this).dialog("destroy");
                        }
                    }
                ]
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

        $(function ($) {
            var block = $(element).find('.profile-block');
            var state = JSON.parse(block.attr('data-state'));

            render(state);

            var show_staff_ui = block.attr('data-show-staff-ui') == 'True';
            if (show_staff_ui) {
                block.find('#staff-debug-info-button')
                    .imdLeanModal()
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
            dialogClass: 'profile-error-modal',
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
        /* The LMS does not use require.js (although it loads it...) */
        xblock($, _);
    } else {
        /* Studio uses require.js */
        require(['jquery', 'underscore'], xblock);
    }
}
