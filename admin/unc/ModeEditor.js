dojo.provide('unc.ModeEditor');

dojo.require("dijit._Widget");
dojo.require("dijit._Templated");
dojo.require('dijit.form.CheckBox');

dojo.ready(function() {
    var M = uow.data.MongoStore;
    
    // deferred version of fetch
    M.prototype.Fetch = function(args) {
        var def = new dojo.Deferred();
        dojo.mixin(args, {
            onComplete: def.callback,
            onError: def.errback
        });
        this.fetch(args);
        return def;
    };
    
    // deferred version of Save
    M.prototype.Save = function() {
        var def = new dojo.Deferred();
        this.save({
            onComplete: def.callback,
            onError: def.errback
        });
        return def;
    };
});

dojo.declare('unc.ModeEditor', [ dijit._Widget, dijit._Templated ], {
    templatePath: dojo.moduleUrl("unc", "ModeEditor.html"),
    widgetsInTemplate: true,
    
    roles: [ 'admin', 'author', 'identified', 'anonymous' ],
    modes: 'crRud',
    
    postCreate: function() {
        var self = this;
        self.inherited(arguments);
        
        self.name.attr('value', 'catalog');
        
        self.connect(self.loginButton, 'onClick', function() {
            uow.triggerLogin().then(dojo.hitch(self, 'checkUser'));
        });
        
        self.checkUser();
    },
        
    checkUser: function() {
        var self = this;
        
        uow.getUser().then(function(user) {
            if (['superuser', 'developer'].indexOf(user.role) >= 0) {
                // no need to login
                dojo.query('#loginMsg').addClass('hidden');
                self.welcomeMsg.innerHTML = 'Welcome ' + user.first_name;
            } else {
                dojo.query('#loginMsg').removeClass('hidden');
                self.welcomeMsg.innerHTML = '';
            }
            self.openModes();
        });
    },
        
    openModes: function() {
        var self = this;
        uow.getDatabase({
            database: 'Admin',
            collection: 'AccessModes',
            mode: 'crud'
        }).then(function(s) { self.modeStore = s; });
        
        self.connect(self.openButton, 'onClick', 'listCollections');
        self.connect(self.saveButton, 'onClick', 'savePermissions');
    },
    
    savePermissions: function() {
        var self = this;
        
        dojo.forEach(self.collections, function(collection) {
            dojo.forEach(self.roles, function(role) {
                var mode = [];
                dojo.forEach(self.modes, function(p) {
                    var id = collection + '-' + role + '-' + p;
                    if (dijit.byId(id).attr('value')) {
                        mode.push(p);
                    }
                });
                var newMode = mode.join('');
                var item;
                if (self.perms[collection] && self.perms[collection][role]) {
                    // previously had a value
                    item = self.perms[collection][role];
                    if (newMode != item.permission) {
                        // change the existing permission
                        self.modeStore.setValue(item, 'permission', newMode);
                    }
                } else if (newMode) {
                    // didn't have a value before but does now
                    item = {
                        database: self.dbName,
                        collection: collection,
                        role: role,
                        permission: newMode
                    };
                    item = self.modeStore.newItem(item);
                    self.recordMode(collection, role, item);
                }
            });
        });
        self.modeStore.Save().then(function() {
            self.welcomeMsg.innerHTML = 'Permissions saved';
        });
    },
    
    listCollections: function() {
        var self = this;

        self.dbName = self.name.attr('value');
        
        uow.manageDatabase(self.dbName).then(function(s) { 
            self.collectionStore = s;
            return s.Fetch({ query: {} });
        }).then(function(collections) {
            self.collections = dojo.map(collections, function(collection) {
                return collection._id; });
            self.collections.sort();
            self.getModes();
        });
    },
    
    recordMode: function(collection, role, item) {
        var self = this;
        var perms = self.perms;
        if (!perms[collection]) {
            perms[collection] = {};
        }
        perms[collection][role] = item;
    },
    
    getModes: function() {
        var self = this;
        self.perms = {};
        self.modeStore.Fetch({
            query: { database: self.dbName }
        }).then(function(items) {
            dojo.forEach(items, function(item) {
                self.recordMode(item.collection, item.role, item);
            });
            self.buildTable();
        });
    },
    
    buildTable: function() {
        var self = this;
        
        dojo.query('[widgetId]', self.table).forEach(function(item) {
            dijit.byNode(item).destroyRecursive();
        });
        dojo.empty(self.table);
        self.tableHead = dojo.create('thead', {}, self.table);
        self.tableBody = dojo.create('tbody', {}, self.table);
        function th(txt, parent, span) {
            var attr = { innerHTML: txt };
            if (span) {
                attr.colspan = span;
            }
            return dojo.create('th', attr, parent);
        }
        
        function setter(mode, collection, role, parent) {
            dojo.forEach(self.modes, function(perm) {
                var td = dojo.create('td', {}, parent);
                var c = dijit.form.CheckBox({
                    title: perm,
                    id: collection + '-' + role + '-' + perm,
                    checked: mode.indexOf(perm) >= 0});
                dojo.place(c.domNode, td);
            });                
        }
        
        var cg = dojo.create('colgroup', {}, self.table);
        dojo.create('col', {}, cg);
        dojo.forEach(self.roles, function(role) {
            var cg = dojo.create('colgroup', { className: 'selector' }, self.table);
            for(j=0; j<self.modes.length; j++) {
                dojo.create('col', { }, cg);
            }
        });

        var h1 = dojo.create('tr', {}, self.tableHead);
        
        th('Roles', h1);
        dojo.forEach(self.roles, function(role) {
            th(role, h1, self.modes.length);
        });
        var h2 = dojo.create('tr', {}, self.tableHead);
        th('Collections', h2);
        dojo.forEach(self.roles, function(role) {
            dojo.forEach(self.modes, function(p) {
                th(p, h2);
            });
        });
        var perms = self.perms;
        dojo.forEach(self.collections, function(collection) {
            var tr = dojo.create('tr', {}, self.tableBody);
            dojo.create('td', {innerHTML: collection}, tr);
            dojo.forEach(self.roles, function(role) {
                var mode =  perms[collection] && perms[collection][role] &&
                            perms[collection][role].permission || '';
                setter(mode, collection, role, tr);
            });
        });
    }
    
});

