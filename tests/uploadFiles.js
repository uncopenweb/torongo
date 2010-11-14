dojo.require('dojo.io.iframe');

function uploadFile(type) {
    var form = dojo.byId('upload');
    if (!form.file.value) {
        return;
    }
    var tags = form.tags.value.replace(/^\s+|\s+$/g, '');
    if (tags.length === 0) {
        return;
    }
    var def = uow.getDatabase({
        database: 'Media',
        collection: type,
        mode: 'c' });
    def.addCallback(function(db) {
        db.upload({
            form: form,
            load: function(data, ioArgs) {
                console.log('load', data);
                dojo.byId('messages').innerHTML = dojo.toJson(data);
            },
            error: function(msg, ioArgs) {
                console.log('error', msg);
                dojo.byId('messages').innerHTML = msg;
            }
        });
    });
    def.addErrback(function(msg) {
        console.log('open failed');
    });
}

dojo.ready(function() {
    dojo.connect(dijit.byId('audio'), 'onClick', function() { uploadFile('Audio'); });
    dojo.connect(dijit.byId('image'), 'onClick', function() { uploadFile('Image'); });
});

