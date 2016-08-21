/* Javascript for KVXBlock. */
function KVXBlock(runtime, element) {
    var sgaXDMEl = $(element).find('#kvxblock-easyxdm-content')[0];
    var kvCreator = new KVCreator(sgaXDMEl, '92', 'xblock:kvxblock', 'IMD edX');

    var Sort= {
      NAME_ASC: 1,
      NAME_DESC: 2,
      DATE_CREATED_ASC: 3,
      DATE_CREATED_DESC: 4
    };
    var recordButtonElement = $(element).find('#record-button');
    var showVideosElement = $(element).find('#show-videos-button');
    var allVideosElement = $(element).find('#all-videos-container');
    var studentVideosContainerElement = $(element).find('#student-videos-container');
    var recording = false;
    var videosShown = false;
    var setVideoIdHandlerUrl = runtime.handlerUrl(element, 'set_video_id');
    var getAllVideosHandlerUrl = runtime.handlerUrl(element, 'get_all_videos');
    var currentSort = Sort.NAME_ASC;
    var searchTimeoutId = undefined;
    var activeVideoWrapper = undefined;

    recordButtonElement.click(function() {
        if (hasVideo()) {
            $( "#dialog-confirm" ).dialog({
                resizable: false,
                height: 130,
                modal: true,
                dialogClass: 'dialog-confirm-delete-video',
                buttons: {
                    "Delete video": function() {
                        $( this ).dialog( "close" );
                        setVideoId('');
                    },
                    Cancel: function() {
                        $( this ).dialog( "close" );
                    }
                }
            });
        }
        else {
            if (recording) {
                kvCreator.close();
                recording = false;
                updateUI();
            }
            else {
                if (!videosShown) {
                    toggleShowVideos()
                }
                recording = true;
                updateUI();
                kvCreator.open(function(context, videoId) {
                    kvCreator.close();
                    recording = false;
                    setVideoId(videoId);
                });
            }
        }
    });

    function updateUI() {
        if (hasVideo()) {
            $("#video-playback").show();
            recordButtonElement.html('Delete Video');
        }
        else {
            $("#video-playback").hide();
            if (recording) {
                recordButtonElement.html('Cancel Recording');
            }
            else {
                recordButtonElement.html('Add Video');
            }
        }
    }

    $(element).find('#input-username').keyup(function() {
        window.clearTimeout(searchTimeoutId);
        searchTimeoutId = window.setTimeout(function() {
            updateVideosElement();
        }, 500);
    });

    $(element).find('#search-clear-search').click(function() {
        $(element).find('#input-username').val('');
        updateVideosElement();
    });

    $(element).find('#sort-username').click(function() {
        if (currentSort == Sort.NAME_ASC) {
            currentSort = Sort.NAME_DESC;
        }
        else {
            currentSort = Sort.NAME_ASC;
        }
        updateVideosElement();
    });

    $(element).find('#sort-date-created').click(function() {
        if (currentSort == Sort.DATE_CREATED_ASC) {
            currentSort = Sort.DATE_CREATED_DESC;
        }
        else {
            currentSort = Sort.DATE_CREATED_ASC;
        }
        updateVideosElement();
    });

    function toggleShowVideos() {
        if (videosShown) {
            allVideosElement.hide();
            showVideosElement.html('Show Videos');
            videosShown = false;
        }
        else {
            allVideosElement.show();
            showVideosElement.html('Hide Videos');
            videosShown = true;
        }
    }

    showVideosElement.click(function() {
        toggleShowVideos()
    });

    function updateVideoUrl(mp4Url, hlsUrl, kuluId, thumbnailUrl, dateCreated) {
        var el = $(element).find('#my-video');
        el.attr("data-kulu-id", kuluId);
        el.attr("data-mp4-url", mp4Url);
        el.attr("data-hls-url", hlsUrl);
        el.attr("data-thumbnail-url", thumbnailUrl);
        var createdDateEl = $(element).find('.video-playback .myvideo-created');
        createdDateEl.text('created ' + dateCreated);
        loadStudentVideo();
        updateUI();
    }

    function hasVideo() {
        var el = $(element).find('#my-video');
        var url = el.attr("data-kulu-id");
        return Boolean(url);
    }

    function updateVideoCount(count) {
        $(element).find('#video-count').html('[' + count + ']');
    }

    function sortVideos(videoNodes) {
        var sortNameAscending = function(a, b) {
            var aName = a.getAttribute('data-video-name');
            var bName = b.getAttribute('data-video-name');
            return aName.localeCompare(bName);
        }
        var sortNameDescending = function(a, b) {
            var aName = a.getAttribute('data-video-name');
            var bName = b.getAttribute('data-video-name');
            return bName.localeCompare(aName);
        }
        var sortDateCreatedAscending = function(a, b) {
            var aDate = a.getAttribute('data-video-created');
            var bDate = b.getAttribute('data-video-created');
            return aDate.localeCompare(bDate);
        }
        var sortDateCreatedDescending = function(a, b) {
            var aDate = a.getAttribute('data-video-created');
            var bDate = b.getAttribute('data-video-created');
            return bDate.localeCompare(aDate);
        }
        var sortFunc = undefined;

        switch (currentSort) {
            case Sort.NAME_ASC:
                sortFunc = sortNameAscending;
                $(element).find('#username-sort-descending-icon').hide();
                $(element).find('#username-sort-ascending-icon').show();
                break;
            case Sort.NAME_DESC:
                sortFunc = sortNameDescending;
                $(element).find('#username-sort-descending-icon').show();
                $(element).find('#username-sort-ascending-icon').hide();
                break;
            case Sort.DATE_CREATED_ASC:
                sortFunc = sortDateCreatedAscending;
                $(element).find('#date-sort-descending-icon').hide();
                $(element).find('#date-sort-ascending-icon').show();
                break;
            case Sort.DATE_CREATED_DESC:
                sortFunc = sortDateCreatedDescending;
                $(element).find('#date-sort-descending-icon').show();
                $(element).find('#date-sort-ascending-icon').hide();
                break;
            default:
                sortFunc = sortNameAscending;
        }

        if (currentSort === Sort.NAME_ASC || currentSort === Sort.NAME_DESC) {
            $(element).find('#sort-username').removeClass('sort-inactive');
            $(element).find('#sort-username').addClass('sort-active');
            $(element).find('#sort-date-created').removeClass('sort-active');
            $(element).find('#sort-date-created').addClass('sort-inactive');
        }
        else {
            $(element).find('#sort-username').removeClass('sort-active');
            $(element).find('#sort-username').addClass('sort-inactive');
            $(element).find('#sort-date-created').removeClass('sort-inactive');
            $(element).find('#sort-date-created').addClass('sort-active');
        }

        videoNodes.sort(sortFunc);
    }

    function updateVideosElement() {
        var videoNodes = studentVideosContainerElement.children();

        var searchString = $(element).find('#input-username').val().toLowerCase();
        if (searchString.length > 0) {
            videoNodes.each(function (index) {
                var videoName = this.getAttribute('data-video-name');
                if (videoName.toLowerCase().indexOf(searchString) === 0) {
                    $(this).show();
                }
                else {
                    $(this).hide();
                }
            });
        }
        else {
            videoNodes.show();
        }

        var visibleVideoNodes = videoNodes.filter(":visible");
        sortVideos(visibleVideoNodes);
        visibleVideoNodes.detach().appendTo(studentVideosContainerElement);

        initialiseVideoGrid(videoNodes.length);
    }

    function generateNodes(allVideos) {
        studentVideosContainerElement.empty();
        var htmlArray = [];
        _.each(allVideos, function(video) {
            if (video.video_kulu_id) {
                var html =  '<div class="student-video" data-video-name="' + video.name + '" data-video-created="' + video.video_date_created_iso + '">' +
                              '<div class="video-username">' + video.name + '</div>' +
                              '<div class="video-date-created">' + video.video_date_created + '</div>' +
                              '<div class="video-wrapper" data-kulu-id="' + video.video_kulu_id + '" data-mp4-url="' + video.video_mp4_url + '" data-hls-url="' + video.video_hls_url + '">' +
                                '<img class="video-thumbnail" src="' + video.video_thumbnail_url + '">' +
                                '<i class="video-default-image fa fa-film"></i>' +
                                '<i class="video-playback-button fa fa-play-circle"></i>' +
                              '</div>' +
                            '</div>';
                htmlArray.push(html);
            }
        });
        var htmlString = htmlArray.join('');
        studentVideosContainerElement.html(htmlString);
        studentVideosContainerElement.find('.video-thumbnail').each(function() {
          var videoThumbnail = $(this);
          var defaultVideoImage = videoThumbnail.next();
          var videoThumbnailSrc = videoThumbnail.attr('src');
          function showDefaultVideoImage() {
            videoThumbnail.hide();
            defaultVideoImage.show();
          }
          if (!videoThumbnailSrc) {
            showDefaultVideoImage();
          }
          videoThumbnail.on('error', function() {
            showDefaultVideoImage();
          });
        });
        $(element).find('.video-wrapper').click(function() {
            if (activeVideoWrapper != this) {
              if (activeVideoWrapper) {
                var thumbnailImg = $(activeVideoWrapper).find('.video-thumbnail');
                thumbnailImg.show();
                var player = videojs('student-video-player');
                player.dispose();
              }
              activeVideoWrapper = this;
              playStudentVideo($(this));
            }
        });
        updateVideoCount(htmlArray.length);
    }

    function playStudentVideo(wrapperEl) {
      var videoEl = $(document.createElement('video'));
      videoEl.attr('id', 'student-video-player');
      videoEl.attr('class', 'video-js vjs-default-skin');
      videoEl.attr('width', '200');
      videoEl.attr('height', '140');
      videoEl.attr('controls', ' ');
      videoEl.attr('preload', 'auto');
      videoEl.attr('data-setup', '{}');
      videoEl.attr('autoplay', 'true');
      wrapperEl.append(videoEl);
      var player = videojs(videoEl[0], {
        playbackRates:[0.75,1,1.25,1.5,1.75,2],
        controlBar: {
          children: ['playToggle', 'volumeMenuButton', 'currentTimeDisplay', 'timeDivider', 'durationDisplay', 'progressControl', 'liveDisplay', 'remainingTimeDisplay', 'customControlSpacer', 'playbackRateMenuButton', 'chaptersButton', 'descriptionsButton', 'subtitlesButton', 'captionsButton', 'fullscreenToggle']
        }
      }, function() {
        $(player.el()).find('.vjs-playback-rate').hide();
        videoEl[0].onplay = function() {
            stopOtherVideoPlayback(this);
        }
        player.on('fullscreenchange', function() {
            if (player.isFullscreen()) {
                $(player.el()).find('.vjs-playback-rate').show();
            }
            else {
                $(player.el()).find('.vjs-playback-rate').hide();
            }
        });

        var thumbnailImg = wrapperEl.find('.video-thumbnail');
        thumbnailImg.hide();

        var mp4_url = wrapperEl.attr("data-mp4-url");
        var mp4_mime_type = 'video/mp4';
        var hls_url = wrapperEl.attr("data-hls-url");
        var hls_mime_type = 'application/vnd.apple.mpegURL';

        if ((mp4_url && player.canPlayType(mp4_mime_type)) ||
            (hls_url && player.canPlayType(hls_mime_type))) {

            player.src([
                { type: mp4_mime_type, src: mp4_url },
                { type: hls_mime_type, src: hls_url }
            ]);
        }
      });
    }

    function updateVideos() {
        $.ajax({
            type: "POST",
            url: getAllVideosHandlerUrl,
            data: JSON.stringify({}),
            success: function(result) {
                var allVideos = JSON.parse(result.all_videos);
                generateNodes(allVideos);
                updateVideosElement();
            }
        });
    }

    function setVideoId(videoId) {
        $.ajax({
            type: "POST",
            url: setVideoIdHandlerUrl,
            data: JSON.stringify({
                "kulu_id": videoId
            }),
            success: function(result) {
                updateVideos();
                updateVideoUrl(result.video_mp4_url, result.video_hls_url, result.video_kulu_id, result.video_thumbnail_url, result.video_date_created);
            },
            error: function(jqXHR, textStatus, errorThrown) {
                errorDialog(".kvxblock_block", 'Set Video', 'An error occurred on the server.');
                updateUI();
            }
        });
    }

    function initialiseVideoGrid(nodeCount) {
        var wasHidden = !allVideosElement.is(":visible");
        allVideosElement.show();
        if (nodeCount > 0) {
          studentVideosContainerElement.shapeshift({
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
        }
        if (wasHidden) {
            allVideosElement.hide();
        }
    }

    function stopOtherVideoPlayback(startedVideoElement) {
        var videoElements = allVideosElement.find('video');
        videoElements.each(function() {
            if (this !== startedVideoElement) {
                this.pause();
            }
        });
    }

    function initialiseStudentVideo(callback) {
        var el = $(element).find('#my-video');
        videojs(el[0], {playbackRates:[0.75,1,1.25,1.5,1.75,2]}, function() {
          loadStudentVideo();
          var player = el[0];
          player.onplay = function() {
              stopOtherVideoPlayback(player);
          }
          if (callback) {
            callback();
          }
        });
    }

    function loadStudentVideo() {
        var el = $(element).find('#my-video');
        var playVideoError = $(element).find('.video-playback .play-video-error');
        var createdDateEl = $(element).find('.video-playback .myvideo-created');
        playVideoError.hide();
        createdDateEl.show();
        loadVideoElement(el, function() {
            playVideoError.text('The video is processing. Please refresh the page after a while.');
            playVideoError.show();
            createdDateEl.hide();
        });
    }

    function loadVideoElement(el, errorFunc) {
        var mp4_url = el.attr("data-mp4-url");
        var mp4_mime_type = 'video/mp4';
        var hls_url = el.attr("data-hls-url");
        var hls_mime_type = 'application/vnd.apple.mpegURL';
        var thumbnailUrl = el.attr("data-thumbnail-url");

        player = videojs(el[0]);

        if ((mp4_url && player.canPlayType(mp4_mime_type)) ||
            (hls_url && player.canPlayType(hls_mime_type))) {

            player.src([
                { type: mp4_mime_type, src: mp4_url },
                { type: hls_mime_type, src: hls_url }
            ]);
            player.poster(thumbnailUrl);
            player.show();
        }
        else {
            player.hide();
            if (errorFunc) {
                errorFunc();
            }
        }
    }

    function errorDialog(appendTo, title, message, onOkFunc) {
        $("<div>" + message + "</div>").dialog({
            appendTo: appendTo,
            resizable: false,
            modal: true,
            dialogClass: 'kvxblock-error-modal',
            title: title,
            buttons: {
                'OK': function() {
                    $(this).dialog("close");
                    onOkFunc();
                }
            }
        });
    }

    $(function ($) {
        updateVideos();
        initialiseStudentVideo(function() {
          updateUI();
        });
    });
}
