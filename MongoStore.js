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

dojo.declare('uow.data.MongoStore', [dojox.data.JsonRestStore], {
    constructor: function(options){
        // monkey patch service._getRequest to insert an additional header
        if (options.accessKey) {
            var _getRequest = this.service._getRequest;
            var myKey = options.accessKey;
            var myGetRequest = function(id, args) {
                var request = _getRequest(id, args);
                request.headers['Authorization'] = myKey;
                return request;
            };
            this.service._getRequest = myGetRequest;
        }
    },
    _doQuery: function(args) {
        //console.log('doQuery', args);
        // pack the query into one parameter with the query args json and uri encoded
        // undefined won't json decode, make it an empty query
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
    }

    // @todo add methods for dealing with collections
});
