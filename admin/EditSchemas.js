dojo.require('unc.GenericEditor');
dojo.require('dojo.DeferredList');

dojo.declare('EditSchemas', null, {
    constructor: function() {
        this.inherited(arguments);
        
        layout = [
            {
                field: 'database',
                name: 'Database',
                width: '50%'
            },
            {
                field: 'collection',
                name: 'Collection',
                width: '50%'
            },
        ];

        // get the schema
        var schema;
        var d1 = dojo.xhrGet({
            url: 'SchemasSchema.json',
            handleAs: 'json'
        }).then(function(s) { schema = s; });
        // get the store
        var store;
        var d2 = uow.getDatabase({
            database: 'Admin',
            collection: 'Schemas',
            mode: 'crud'
        }).then(function(s) { store = s; });
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
    var e = new EditSchemas();
});

