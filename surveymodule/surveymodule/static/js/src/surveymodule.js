/* Javascript for SurveyXBlock. */


function SurveyXBlock(runtime, element) {

    function updateUserInfo(result) {
        var resultJson = $.parseJSON(result)
        // console.log(resultJson.loadingGifUrl);
        if(resultJson.isStuffMemeber){
          $("#debugButton").show();
          $("#debugButton").click(function() {
              $("#userInfo").toggle();
              if($("#userInfo").is(":visible")){
                $("#debugButton").text("hide debug view");
              }
              else{
                $("#debugButton").text("show debug view");
              }
          });
          $('#userInfo', element).text(result);
          $('#userInfo').hide();
          if((!resultJson.surveyId) || resultJson.surveyId === ""){
            $("#notConfigured").show();
          }
          else{
            $("#notConfigured").hide();
          }
        }
        else{
          $("#debugButton").hide();
        }
        var socialUserID = resultJson.socialUserID;
        var vip = "";
        console.log(socialUserID);
        if(socialUserID && socialUserID!=""){
          var socilaUserIdParts = socialUserID.split(':');
          if(socilaUserIdParts.length > 1){
              vip = socilaUserIdParts[1];
          }
        }

        if(resultJson.frameSizeHeight > 0){
          $('#surveyFrame').css('height', resultJson.frameSizeHeight + "px");
        }

        if(vip === ""){
          $('#surveyFrame').attr("src","https://imd.co1.qualtrics.com/jfe/form/"+resultJson.surveyId)
        }
        else{
          $('#surveyFrame').attr("src","https://apps.imd.org/fe/Survey/Eval?surveyId="+resultJson.surveyId+"&vip="+vip)
        }
    }

    var getUserUrl = runtime.handlerUrl(element, 'logged_in_username');

    // function displayStuffContent(){
    //   alert("displayStuffContent");
    //   $("#debugButton").show();
    // }

    function updateUserInfoError(error){
        $('#userInfo', element).text(error.responseText);
    }

    $(function ($) {
      $.ajax({
          type: "POST",
          url: getUserUrl,
          data: JSON.stringify({"param":"value"}),
          success: updateUserInfo,
          error: updateUserInfoError
      });
    });
}
