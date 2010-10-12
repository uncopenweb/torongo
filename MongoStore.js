/*
 * dojo.data store supporting MongoQueries.
 *
 * :requires: Dojo 1.4.x
 * :copyright: Gary Bishop, Peter Parente 2010
 * :license: BSD
**/

dojo.provide('uow.data.MongoStore');
dojo.require('dojox.rpc.Service');
dojo.require('dojox.rpc.Rest');
dojo.require('dojox.data.JsonRestStore');
dojo.require('dojo.io.iframe');

dojo.declare('uow.data.MongoStore', [dojox.data.JsonRestStore], {
    constructor: function(options){
        // monkey patch service._getRequest to insert an additional header
        if (options.accessKey) {
            var _getRequest = this.service._getRequest;
            var myKey = options.accessKey;
            this.accessKey = myKey;
            var myGetRequest = function(id, args) {
                var request = _getRequest(id, args);
                // take the key off the path before using it.
                request.headers['Authorization'] = myKey;
                return request;
            };
            this.service._getRequest = myGetRequest;
        }
    },
    _doQuery: function(args) {
        // pack the query into one parameter with the query args json and uri encoded
        // undefined won't json decode, make it an empty query
        // shallow copy of args so we don't screw up what got handed in
        var Args = {};
        dojo.mixin(Args, args);
        args = Args;
        var qs = {};
        if (args.query && typeof(args.query) == 'string') { // fetchItemByIdentity
            return this.inherited(arguments);
        }
        if (args.query && typeof(args.query) == 'object') {
            qs.mq = encodeURIComponent(dojo.toJson(args.query));
        }
        if (args.sort && typeof(args.sort) != 'undefined') {
            var s = dojo.map(args.sort, function(v) {
                return (v.descending ? '-' : '+') + encodeURIComponent(v.attribute); }).join(',');
            qs.ms = s;
        }
        args.query = qs;
        // hand off to the method in JsonRestStore
        return this.inherited(arguments);
    },
    upload: function(args) {
        // upload a file using io.iframe.send
        // you need to set form, load, and error
        args.url = '/upload/';
        args.method = 'post';
        args.content = { 'Authorization': this.accessKey };
        args.handleAs = 'json';
        dojo.io.iframe.send(args);
    },
    getValue: function(item, property, defaultValue){
        // taken from http://bugs.dojotoolkit.org/attachment/ticket/7175/BeanStore.js
        // summary:
        //    Gets the value of an item's 'property', supports dot-notation
        //
        //    item: /* object */
        //    property: /* string */
        //        property to look up value for    
        //    defaultValue: /* string */
        //        the default value
        
        if (property.indexOf(".") > 0) { //dot-notation
            var matches = property.match(/(\w+)\.([\w\.]+)/);
            if (matches && matches.length > 2) {
                var association = this.getValue(item, matches[1]);
                if (association) {
                    return this.getValue(association, matches[2]);
                }
            }
        }
        else {
            return this.inherited(arguments);
        }
    },
    getMode: function() {
        // return the permission string actually granted
        return this.accessKey.split('-')[0]
    },
    fetchOne: function(args) {
        var def = new dojo.Deferred();
        this.fetch({
            query : args.query,
            onComplete: function(items) {
                if(items.length == 1) {
                    var item = items[0];
                    def.callback(item);
                } else {
                    def.errback(items.length);
                }
            },
            onError: function(err) {
                def.errback(err);
            },
            scope: this
        });
        return def;
    },
    updateOne: function(args) {
        var def = new dojo.Deferred();
        this.fetchOne(args).then(dojo.hitch(this, function(item) {
            for(var attr in args.data) {
                // have to use setValue to set dirty flag
                this.setValue(item, attr, args.data[attr]);
            }
            if(args.save) {
                this.save({
                    onComplete: function() {
                        def.callback(item);
                    },
                    onError: function(err) {
                        def.errback(err);
                    }
                });
            } else {
                def.callback(item);
            }
        }), function(err) {
            def.errback(err);
        });
        return def;
    },
    deleteOne: function(args) {
        var def = new dojo.Deferred();
        this.fetchOne(args).then(dojo.hitch(this, function(item) {
            this.deleteItem(item);
            if(args.save) {
                this.save({
                    onComplete: function() {
                        def.callback(item);
                    },
                    onError: function(err) {
                        def.errback(err);
                    }
                });
            } else {
                def.callback(item);
            }
        }), function(err) {
            def.errback(err);
        });
        return def;
    },
    putOne: function(args) {
        var def = new dojo.Deferred();
        // fetch success case
        this.fetchOne(args).then(dojo.hitch(this, function(item) {
            for(var attr in args.data) {
                // have to use setValue to set dirty flag
                this.setValue(item, attr, args.data[attr]);
            }
            if(args.save) {
                this.save({
                    onComplete: function() {
                        def.callback(item);
                    },
                    onError: function(err) {
                        def.errback(err);
                    }
                });
            } else {
                def.callback(item);
            }
        }),
        // fetch error case
        dojo.hitch(this, function(err) {
            if(err === 0) {
                // create new item from query + data
                dojo.mixin(args.data, args.query);
                var item = this.newItem(args.data);
                if(args.save) {
                    this.save({
                        onComplete: function() {
                            def.callback(item);
                        },
                        onError: function(err) {
                            def.errback(err);
                        }
                    });
                } else {
                    def.callback(item);
                }                
            } else {
                // more than one match
                def.errback(err);
            }
        }));
        return def;
    }
});

// Gets a MongoStore instance (like dojox.data.JSONRestStore)
uow.data.getDatabase = function(args) {
    var defargs = { idAttribute: '_id',
                    mode: 'crud' };
    args = args || {};
    args = dojo.mixin(defargs, args);
    var xhr = {
        url: '/data/_auth',
        handleAs: 'json',
        postData: dojo.toJson({
            database: args.database,
            collection: args.collection,
            mode: args.mode
        }),
        headers: { "Content-Type": "application/json" }
    };

    var def = new dojo.Deferred();
    dojo.xhrPost(xhr).addCallback(function(response) {
        args.target = response.url;
        args.accessKey = response.key;
        def.callback(new uow.data.MongoStore(args));
    }).addErrback(function(err) {
        def.errback(err);
    });
    return def;
};

// Return a store for listing and deleting collections from a database
uow.data.manageDatabase = function(args) {
    args = args || {};
    return uow.data.getDatabase({
        database: args.database,
        collection: '*',
        mode: 'rd'
    });
};

// Ask the server to return the current user
uow.data.getUser = function(args) {
    return dojo.xhrGet( {
        url: '/data/_auth/user',
        handleAs: 'json'
    } );
};

// Create an empty collection
uow.data.touchCollection = function(args) {
    var def = new dojo.Deferred();
    uow.data.getDatabase({
        database : args.database,
        collection : args.collection
    }).then(function(db) {
        var item = db.newItem({foo : 'bar'});
        //console.log(db.isItem(item));
        //console.log(item);
        db.save({
            onComplete: function() {
                //console.log(db.isItem(item));
                //console.log(item);
                db.deleteItem(item);
                db.save({
                    onComplete: function() {
                        //console.log('finished delete');
                        def.callback(db);
                    },
                    onError: function() {
                        //console.log('failed delete');
                        // error deleting, but collection does exist now
                        def.callback(db);
                    }
                });
            },
            onError: function(err) {
                def.errback(err);
            }
        });
    }, function(err) {
        def.errback(err);
    });
    return def;
};

// Set the permissions for a user role in a db/collection
uow.data.setAccess = function(args) {
    var def = new dojo.Deferred();
    uow.data.getDatabase({
        database : 'Admin',
        collection : 'AccessModes',
        mode : 'crud'
    }).then(function(db) {
        var key = {
            database : args.database,
            collection : args.collection,
            role : args.role
        };
        if(args.permission === null) {
            return db.deleteOne({
                query: key,
                save: true
            });
        } else {
            return db.putOne({
                query : key,
                data : {permission : args.permission},
                save: true
            });
        }
    }, function(err) {
        def.errback(err);
    }).then(function(item) {
        def.callback(item);
    }, function(err) {
        def.errback(err);
    });
    return def;
};

// Set the role for user in a db/collection
uow.data.setRole = function(args) {
    var def = new dojo.Deferred();
    uow.data.getDatabase({
        database : 'Admin',
        collection : 'AccessUsers',
        mode : 'crud'
    }).then(function(db) {
        var key = {user : args.user};
        if(args.role === null) {
            return db.deleteOne({
                query: key,
                save: true
            });
        } else {
            return db.putOne({
                query : key,
                data : {role : args.role},
                save: true
            });
        }
    }, function(err) {
        def.errback(err);
    }).then(function(item) {
        def.callback(item);
    }, function(err) {
        def.errback(err);
    });
    return def;
};

// Set the schema for a db/collection
uow.data.setSchema = function(args) {
    var def = new dojo.Deferred();
    uow.data.getDatabase({
        database : 'Admin',
        collection : 'Schemas',
        mode : 'crud'
    }).then(function(db) {
        var key = {
            database : args.database,
            collection : args.collection
        };
        if(args.schema === null) {
            return db.deleteOne({
                query: key,
                save: true
            });
        } else {
            return db.putOne({
                query : key,
                data : {schema : args.schema},
                save: true
            });
        }
    }, function(err) {
        def.errback(err);
    }).then(function(item) {
        def.callback(item);
    }, function(err) {
        def.errback(err);
    });
    return def;
};
