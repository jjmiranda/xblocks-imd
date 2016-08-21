(function($){

  var zIndex = 10000;
  function pushZIndex() {
    zIndex += 100;
  }
  function popZIndex() {
    zIndex -= 100;
  }

  $.fn.extend({

    imdLeanModal: function(options) {

      var defaults = {
        top: 100,
        overlay: 0.5,
        closeButton: null,
        closeOnOverlayClick: true,
        onOpenFunc: null
      }

      options =  $.extend(defaults, options);

      function overlayId(modal_id) {
        return modal_id.replace('#', '') + '-overlay';
      }

      return this.each(function() {

        var o = options;

        $(this).click(function(e) {

          if (options.onOpenFunc && options.onOpenFunc()) {
            return;
          }

          var modal_id = $(this).attr("href");
          var overlay = $(document.createElement( "div" ));
          overlay.attr("id", overlayId(modal_id));
          $("body").append(overlay);

          pushZIndex();

          overlay.css({
            'position': 'fixed',
            'z-index': zIndex,
            'top': '0px',
            'left': '0px',
            'height': '100%',
            'width': '100%',
            'background': '#000',
            'display': 'none'
          });

          if (options.closeOnOverlayClick) {
            overlay.click(function() {
              close_modal(modal_id);
            });
          }

          $(o.closeButton).off('click').click(function() {
            close_modal(modal_id);
          });

          var modal_height = $(modal_id).outerHeight();
          var modal_width = $(modal_id).outerWidth();

          overlay.css({
            'display' : 'block',
            'opacity' : 0
          });

          overlay.fadeTo(200,o.overlay);

          $(modal_id).css({

            'display' : 'block',
            'position' : 'fixed',
            'opacity' : 0,
            'z-index': zIndex + 50,
            'left' : 50 + '%',
            'margin-left' : -(modal_width/2) + "px",
            'top' : o.top + "px"

          });

          $(modal_id).fadeTo(200,1);

          e.preventDefault();

        });

      });

      function close_modal(modal_id){

        var overlay = $('#' + overlayId(modal_id));
        overlay.fadeOut({
            duration: 200,
            complete: function() {
                overlay.remove();
                popZIndex();
            }
        });

        $(modal_id).css({ 'display' : 'none' })
            .trigger("imdLeanModal:close");
      }

    }
  });

})(jQuery);
