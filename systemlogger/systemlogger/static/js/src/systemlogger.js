/* Javascript for SystemLoggerXBlock. */

function GetBrowserInfo(){
  var ua=navigator.userAgent,tem,M=ua.match(/(opera|chrome|safari|firefox|msie|trident(?=\/))\/?\s*(\d+)/i) || [];
  if(/trident/i.test(M[1])){
      tem=/\brv[ :]+(\d+)/g.exec(ua) || [];
      return {name:'IE',version:(tem[1]||'')};
      }
  if(M[1]==='Chrome'){
      tem=ua.match(/\bOPR\/(\d+)/)
      if(tem!=null)   {return {name:'Opera', version:tem[1]};}
      }
  M=M[2]? [M[1], M[2]]: [navigator.appName, navigator.appVersion, '-?'];
  if((tem=ua.match(/version\/(\d+)/i))!=null) {M.splice(1,1,tem[1]);}
  return {
    name: M[0],
    version: M[1]
  };
 }


function SystemLoggerXBlock(runtime, element) {

  var Columns = {
      Username: 0,
      Browser: 1,
      Flash: 2,
      System: 3,
      LastAccess: 4,
      Error: 5
  };

    var minimumFlashVersion = 9;

    var minimumFirefoxVersion = 42;

    var minimumChromeVersion = 46;

    var minimumSafariVersion = 7;

    var lastSortList = [[0, 0]];

    var tableDisplayed = false;

    var browserDetails = GetBrowserInfo();

    var browserString = browserDetails.name+"   "+browserDetails.version;

    var playerVersion = swfobject.getFlashPlayerVersion();

    var flashPlayerString = playerVersion.major+"."+playerVersion.minor+"."+playerVersion.release;

    var agentParams = navigator.userAgent.split('(');

    var osString = "unknown";

    var searchTimeoutId = undefined;

    var hasBrowserError = false;

    if(agentParams.length > 1){

      osString = navigator.userAgent.split('(')[1].split(')')[0]
    }

    $("#browserDetails").html("You are running on <b>"+browserDetails.name+"</b> with version <b>"+browserDetails.version+"<b>");

    $("#flashDetails").html("&nbsp; and with flash version:  "+flashPlayerString+".");

    if(browserDetails.name != 'Chrome' && browserDetails.name != 'Firefox' && browserDetails.name != 'Safari'){
      if(browserDetails.name != 'IE' || (browserDetails.name === 'IE' && browserDetails.version < 11)){
        document.getElementById("wrongBrowser").style.display = "block";
        hasBrowserError = true;
      }
    }
    else if((browserDetails.name === 'Firefox' && browserDetails.version < minimumFirefoxVersion) ||
    (browserDetails.name === 'Safari' && browserDetails.version < minimumSafariVersion) ||
    (browserDetails.name === 'Chrome' && browserDetails.version < minimumChromeVersion)){
      document.getElementById("wrongBrowser").style.display = "block";
      hasBrowserError = true;
    }

    if(playerVersion.major < minimumFlashVersion){
      document.getElementById("wrongFlash").style.display = "block";
    }
    else{
      document.getElementById("wrongFlash").style.display = "none";
    }

    $(element).find('#input-username').keyup(function() {
        window.clearTimeout(searchTimeoutId);
        searchTimeoutId = window.setTimeout(function() {
            filterStudents();
        }, 500);
    });

    $(element).find('#search-clear-search').click(function() {
        $(element).find('#input-username').val('');
        filterStudents();
    });

    $(element).find('#csv-export').click(function () {

          var csvData = '';
          $('#stats-table').find("tbody").children().each(function (index)
          {
            if ($(this).is(":visible")){
              var dataItems = $(this).find('td')//.splice(',')+'\n';
              for(var i=0; i< dataItems.length; i++){
                dataItems[i] = $(dataItems[i]).text();
              }
              csvData += dataItems.splice(',')+'\n';;
            }
          });
          var filename = "userdata.csv";
          var blob = new Blob([csvData], {type: 'text/csv;charset=utf-8;'});
          if (navigator.msSaveBlob) { // IE support
              navigator.msSaveBlob(blob, filename);
          } else {
              var url = URL.createObjectURL(blob);
              downloadLink(url, filename);
          }
    });

    function downloadLink(url, filename) {
            var link = document.createElement("a");
            link.setAttribute("href", url);
            link.setAttribute("download", filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

    function filterStudents()
    {
      var searchString = $('#input-username').val().toLowerCase();
      var tableNodes = $('#stats-table').find("tbody").children();

      $('#stats-table').find("tbody").children().each(function (index)
      {
        var dataString = $(this).find('td').text();
        if (searchString.length == 0 || dataString.toLowerCase().indexOf(searchString) >= 0){
              $(this).show();
        }
        else{
          $(this).hide();
        }
      });
    }

    function postResultComplete(result){

    }

    function updateResult(result) {

      $("#loadingContainer").hide();

        function columnIndexFromColumnId(columnId) {
          var columnOrder = [Columns.Username, Columns.Browser, Columns.Flash, Columns.System, Columns.LastAccess, Columns.Error];
          return columnOrder.indexOf(columnId);
        }

        function initialiseTable() {
            var headersConfig = {};
            headersConfig[columnIndexFromColumnId(Columns.FeedbackFile)] = { sorter: false };

            $("#stats-table").tablesorter({
                headers: headersConfig,
                sortList: lastSortList
            })
            .bind("sortEnd",function(sorter) {
                lastSortList = sorter.target.config.sortList;
            });
            $("#stats-table").trigger("update");
        }

        $("#stats-table").find("tr:gt(0)").remove();

        var allUsers = result.length;
        var activeUsers = 0;
        var okBrowsers = 0;
        var nonOkBrowsers = 0;

        $.each(result, function(i, item) {

            if(item.Browser){
              activeUsers ++;
              if(item.Error){
                nonOkBrowsers++;
              }
              else{
                okBrowsers++;
              }
            }

            var tr = $('<tr>').append(
                $('<td>').html(" <a href=\"/courses/"+item.CourseId+"/progress/"+item.UserId+"\">"+item.UserName+"</a> <p style=\"margin: 0px;\">(<a href=\"/u/"+item.UserName+"\" target=\"blank\">"+item.UserName+"</a>)</p>"),
                $('<td>').text(item.Browser),
                $('<td>').text(item.System),
                $('<td>').text(item.Flash),
                $('<td>').text(item.LastAccess !== "" ? moment(item.LastAccess).format('MM/DD/YYYY HH:mm:ss') : ""),
                $('<td>').html(
                  item.Error?"<span style=\"display:none;\">1</span><img src='/xblock/resource/systemlogger/public/images/Error-20.png' alt='Browser in not among the compatibility list.'/>":
                  item.Browser === "" ? "<span style=\"display:none;\">-1</span>":
                  "<span style=\"display:none;\">0</span><img src='/xblock/resource/systemlogger/public/images/Ok-20.png'/>")
            );
            $('#stats-table').append(tr);
        });

        $('#studentsCount').text(allUsers);

        $('#compatibleBrowsers').text(okBrowsers);

        $('#uncompatibleBrowsers').text(nonOkBrowsers);

        $('#unactiveUsers').text(allUsers - activeUsers);

        $("#titleStats").show();

        $("#stats-table").show();

        $("#searchArea").show();

        $("#stats-button").text("Hide Participants Statistics");

        tableDisplayed = true;

        initialiseTable();

        console.log(result);
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

    var postDataUrl = runtime.handlerUrl(element, 'updateDetails');
    var readDataUrl = runtime.handlerUrl(element, 'readDetails');

    $.ajax({
        type: "POST",
        url: postDataUrl,
        data: JSON.stringify({"browser": browserString, "flash":flashPlayerString, "osstring": osString, "browserError":hasBrowserError}),
        success: postResultComplete
    });

    $(function ($) {
      $("#stats-button").click(function() {

        if(! tableDisplayed){
          $("#loadingContainer").show();
          $.ajax({
              type: "POST",
              url: readDataUrl,
              data: JSON.stringify(""),
              success: updateResult
          });
        }
        else{
          $("#stats-table").hide();
          $("#searchArea").hide();
          $("#titleStats").hide();
          tableDisplayed = false;
          $("#stats-button").text("Show Participants Statistics");
        }
      });
    });
}
