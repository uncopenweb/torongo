dojo.require('unc.GenericEditor');
dojo.require('dojo.DeferredList');

dojo.declare('EditUsers', null, {
    constructor: function() {
        this.inherited(arguments);
        
        layout = [
            {
                field: 'user',
                name: 'User ID',
                width: '50%'
            },
            {
                field: 'role',
                name: 'Role',
                width: '50%'
            }
        ];

        // get the schema
        var schema;
        var d1 = dojo.xhrGet({
            url: 'AccessUsersSchema.json',
            handleAs: 'json'
        }).then(function(s) { schema = s; });
        // get the store
        var store;
        var d2 = uow.getDatabase({
            database: 'Admin',
            collection: 'AccessUsers',
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
    var e = new EditUsers();
});

