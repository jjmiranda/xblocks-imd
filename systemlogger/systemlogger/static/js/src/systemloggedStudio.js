function SystemLoggerStudioXBlock(runtime, element) {
  var saveUrl = runtime.handlerUrl(element, 'save_inputs');

    var validators = {
        'number': function(x) {
            return Number(x);
        },
        'string': function(x) {
            return !x ? null : x;
        }
    };

    function save() {
        var view = this;
        view.runtime.notify('save', {state: 'start'});
        var isValid = true;

        var data = {};
        $(element).find('input').each(function(index, input) {
            data[input.name] = input.value;
            if(data[input.name] === ""){
              $("#"+input.name+"Error").show();
              isValid = false;
            }
        });

        $(element).find('select').each(function(index, el) {
            data[el.name] = el.value;
        });

        $(element).find('textarea').each(function(index, el) {
            data[el.name] = el.value;
        });

        console.log(data);

        if(isValid)
        {
          $("#inputDislpayNameError").hide();
          $.ajax({
              type: 'POST',
              url: saveUrl,
              data: JSON.stringify(data),
              success: function() {
                  view.runtime.notify('save', {state: 'end'});
              }
          });
        }
    }

    return {
        save: save
    };
}
