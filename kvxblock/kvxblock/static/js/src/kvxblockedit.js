/* Javascript for kvXBlock. */
function kvXBlockInitStudio(runtime, element) {
    var saveUrl = runtime.handlerUrl(element, 'save_kvxblock');

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

        var data = {};
        $(element).find('input').each(function(index, input) {
            data[input.name] = input.value;
        });
        $(element).find('select').each(function(index, el) {
            data[el.name] = el.value;
        });
        $(element).find('textarea').each(function(index, el) {
            data[el.name] = el.value;
        });

        $.ajax({
            type: 'POST',
            url: saveUrl,
            data: JSON.stringify(data),
            success: function() {
                view.runtime.notify('save', {state: 'end'});
            }
        });
    }

    return {
        save: save
    };
}