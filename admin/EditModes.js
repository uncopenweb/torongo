dojo.require('unc.GenericEditor');
dojo.require('dojo.DeferredList');

dojo.declare('EditModes', null, {
    constructor: function() {
        this.inherited(arguments);
        
        layout = [
            {
                field: '_item',
                name: 'Database',
                width: '25%',
                formatter: function(item) { console.log('database', item); return item.database.join(' '); }
            },
            {
                field: '_item',
                name: 'Collection',
                width: '25%',
                formatter: function(item) { console.log('collection', item); return item.collection.join(' '); }
            },
            {
                field: '_item',
                name: 'Role',
                width: '25%',
                formatter: function(item) { console.log('role', item); return item.role.join(' '); }
            },
            {
                field: 'permission',
                name: 'Permission',
                width: '25%'
            }
        ];

        // get the schema
        var schema;
        var d1 = dojo.xhrGet({
            url: 'AccessModesSchema.json',
            handleAs: 'json'
        }).then(function(s) { schema = s; });
        // get the store
        var store;
        var d2 = uow.getDatabase({
            database: 'Admin',
            collection: 'AccessModes',
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
    var e = new EditModes();
});

