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
        if (args.query && typeof(args.query) != 'undefined') {
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
    }


    // @todo add methods for dealing with collections
});
