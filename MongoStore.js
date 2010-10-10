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
                request.url = request.url.replace(/^[^$]+\$/, '');
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
                    console.log('invoking callback with one item');
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
                // create new item
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
        args.target = response.key + '$' + response.url; // add the key to overcome caching of servicesy
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
    
};

// Set the permissions for a user role in a db/collection
uow.data.setAccess = function(args) {
    
};