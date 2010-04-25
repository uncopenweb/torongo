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
    _doQuery: function(args) {
        console.log('doQuery', args);
        // pack the query into one parameter with the query args json and uri encoded
        // undefined won't json decode, make it an empty query
        if (!args.query || typeof(args.query) == 'undefined') args.query = {};
        args.query.mq = encodeURIComponent(dojo.toJson(args.query));
        // hand off to the method in JsonRestStore which ignores the query if queryStr is set
        return this.inherited(arguments);
    }

    // @todo add methods for dealing with collections
});
