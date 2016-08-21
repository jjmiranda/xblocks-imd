
KVCreator = function(easyXDMContainerEl, kvPresentationSubtype, kvPresentationId, kvPresentationPresenter) {

    this.socket = undefined;

    this.open = function(doneFunc, context) {
        $(easyXDMContainerEl).show();

        var PROTOCOL                            = 'https';
        var HOST_NAME_EASY_XDM_PROVIDER         = 'imdbs-creator.kuluvalley.com';
        var NAME_EASYXDM_PROVIDER_FILE          = 'easyXDM.php';
        var NAME_EASYXDM_PROVIDER_HELPER_FILE   = 'name.html';
        var NAME_EASYXDM_PROVIDER_SWF_FILE      = 'easyxdm.swf';
        var PATH_EASYXDM_PROVIDER_FILES         = 'easyxdm';
        var PATH_EASYXDM_CONSUMER_HELPER_FILE   = 'name.html';

        var REGEX_EASYXDM_IFRAME_KEY            = /^easyxdm_(.*)_provider$/i;

        var uriProvider = URI({
            hostname:   HOST_NAME_EASY_XDM_PROVIDER,
            path:       NAME_EASYXDM_PROVIDER_FILE,
            protocol:   PROTOCOL
        });
        var uriSwf = URI({
            hostname: HOST_NAME_EASY_XDM_PROVIDER,
            path:     PATH_EASYXDM_PROVIDER_FILES,
            protocol: PROTOCOL
        });
        var uriRemoteHelper = URI({
            hostname: HOST_NAME_EASY_XDM_PROVIDER,
            path:     PATH_EASYXDM_PROVIDER_FILES,
            protocol: PROTOCOL
        });

        function encodeData(string) {
            var key = "test";
            var words = CryptoJS.enc.Utf16LE.parse(key);
            var md5key = CryptoJS.MD5(words);   // 16 bytes
            md5key.concat(CryptoJS.lib.WordArray.create(md5key.words.slice(0,2)));   // 24 bytes
            var iv = CryptoJS.enc.Hex.parse('0000000000000000');
            var qsWords = CryptoJS.enc.Utf16LE.parse(string);
            var encoded = CryptoJS.TripleDES.encrypt(qsWords, md5key, { iv: iv });
            return encoded;
        }

        var queryProvider = {
            url: URI.build({
                hostname: HOST_NAME_EASY_XDM_PROVIDER,
                protocol: PROTOCOL
            })
        };
        var queryData = {
            type: 'forum',
            subtype: kvPresentationSubtype,
            callback_url: 'https://learn.imd.org/web_services/save_video/',
            id: kvPresentationId,
            presenter: kvPresentationPresenter
        };
        var queryString = URI.decodeQuery(URI.buildQuery(queryData));
        queryProvider.data = encodeData(queryString);
        uriProvider.query(queryProvider);

        uriSwf.filename(NAME_EASYXDM_PROVIDER_SWF_FILE);
        uriSwf.directory(PATH_EASYXDM_PROVIDER_FILES);
        uriRemoteHelper.filename(NAME_EASYXDM_PROVIDER_HELPER_FILE);
        uriRemoteHelper.directory(PATH_EASYXDM_PROVIDER_FILES);

        this.socket = new easyXDM.Socket({
            container:      easyXDMContainerEl,
            local:          PATH_EASYXDM_CONSUMER_HELPER_FILE,
            remote:         uriProvider.toString(),
            remoteHelper:   uriRemoteHelper.toString(),
            swf:            uriSwf.toString(),
            onReady:        function(message, origin) {
                var xdmIFrameElement = $(this.container).children()[0];
                xdmIFrameElement.width = "100%";
                xdmIFrameElement.height = "100%";
            },
            onMessage: function(videoId, origin) {
                doneFunc(context, videoId);
            }
        });
    }

    this.close = function() {
        this.socket.destroy();
        this.socket = undefined;
        $(easyXDMContainerEl).hide();
    }
}
