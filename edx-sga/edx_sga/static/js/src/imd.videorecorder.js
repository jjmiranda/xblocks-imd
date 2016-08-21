
IMDVideoRecorder = function(containerEl, kvPresentationSubtype, kvPresentationId, kvPresentationPresenter) {

  var VIDEO_REC_ORIGIN = 'http://consultant-16';
  var VIDEO_REC_SRC = 'http://consultant-16/fe/video';
  var videoRecUrl = new URI(VIDEO_REC_SRC).query({
    kuluSubtype: kvPresentationSubtype,
    kuluId: kvPresentationId,
    kuluPresenter: kvPresentationPresenter
  });

  this.open = function(doneFunc, context) {
    $(containerEl).show();

    $('<iframe>', {
      src: videoRecUrl.toString(),
      id: 'imd-recorder',
      frameborder: 0,
      scrolling: 'no',
      width: '100%',
      height: '100%'
    }).appendTo(containerEl);

    function listener(event) {
      if (event.origin === VIDEO_REC_ORIGIN) {
        doneFunc(context, event.data);
        $(containerEl).hide();
        $(containerEl).empty();
        window.removeEventListener("message", listener);
      }
    }
    window.addEventListener("message", listener);
  }

  this.close = function() {
    $(containerEl).hide();
    $(containerEl).empty();
  }
}
