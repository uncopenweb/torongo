dojo.require('unc.GenericEditor');
dojo.require('dojo.DeferredList');

dojo.declare('EditModes', null, {
    constructor: function() {
        this.inherited(arguments);
        
        dojo.connect('openButton', 'onClick', this, 'openDB');
    },
    
    openDB: function() {
        var dbName = dijit.byId('dbName').attr('value');
        
        var collectionStore;
        var d1 = uow.getDatabase({
            database: dbName,
            collection: '*',
            mode: 'L'
        }).then(function(s) { collectionStore = s; });
        
        var modeStore;
        var d2 = uow.getDatabase({
            database: 'Admin',
            collection: 'AccessModes',
            mode: 'crud'
        }).then(function(s) { modeStore = s; });
        
        // wait on both to finish
        var d3 = new dojo.DeferredList([d1,d2]);
        
        d3.then(function(L) {
            var editor = new unc.GenericEditor({
                store: store,
                gridLayout: layout,
                schema: schema
            });
            dijit.byId('content').attr('content', editor);
            editor.startup();
        });
    }
            
});

dojo.ready(function() {
    //var e = new EditModes();
});

