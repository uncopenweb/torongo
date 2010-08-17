dojo.provide('unc.ArrayStore');

dojo.require('dojo.data.ItemFileWriteStore');

// We need to copy objects that come from other stores to avoid weirdness with the dojo data structures
function myCopy(obj) {
    if (dojo.isArray(obj)) {
        return dojo.map(obj, function(item) { return myCopy(item); });
    } else if (typeof(obj) === 'object') {
        var result = {};
        for (var prop in obj) {
            if (!prop.match(/^_/)) {
                result[prop] = myCopy(obj[prop]);
            }
        }
        return result;
    } else {
        return obj;
    }
}

dojo.declare('unc.ArrayStoreClass', [ dojo.data.ItemFileWriteStore ], {
    arrayValueToReturn : [],
    
    _saveEverything: function(saveCompleteCallback, saveErrorCallback, jsonString) {
        var obj = dojo.fromJson(jsonString);
        this.arrayValueToReturn = obj.items;
        saveCompleteCallback();
    },
    
    toArray: function() {
        this.save();
        return this.arrayValueToReturn;
    }
});

unc.ArrayStore = function(ary) {
    ary = myCopy(ary);
    var obj = { items: ary };
    return new unc.ArrayStoreClass({ data: obj });
};

