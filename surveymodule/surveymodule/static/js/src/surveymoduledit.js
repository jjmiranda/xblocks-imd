/* Javascript for kvXBlock. */
function SurveyXBlockInitStudio(runtime, element) {
    var saveUrl = runtime.handlerUrl(element, 'save_surveyblock');

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

        if(isValid)
        {
          $("#inputDislpayNameError").hide();
          $("#inputSurveyIDError").hide();
          $("#frameSizeHeightError").hide();
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
