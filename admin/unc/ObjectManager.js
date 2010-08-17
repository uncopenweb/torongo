dojo.provide('unc.ObjectManager');

dojo.require('dijit._Templated');
dojo.require('dijit._Widget');
dojo.require('dijit._Container');

dojo.declare('unc.ObjectManager', [ dijit._Widget, dijit._Templated, dijit._Container ], {
    templatePath: dojo.moduleUrl("unc", "ObjectManager.html"),
    widgetsInTemplate: true,

    generator: null,
    schema: {},
    name: "",
    title: "",
    init: [],
    description: "",

    postCreate: function() {
        this.inherited(arguments);

        //console.log('postCreate ObjectManager', this.containerNode, this.init);
        for(var propertyName in this.schema.properties) {
            var property = this.schema.properties[propertyName];
            this.generator(propertyName, property, this.init && this.init[propertyName] || null,
                           this.containerNode);
            dojo.create('br', {clear:'all'}, this.containerNode);
        }
    },

    _getValueAttr: function() {
        var children = this.getChildren();
        //console.log('OM value', children);
        var result = {};
        dojo.forEach(children, function(child) {
            result[child.name] = child.attr('value');
        }, this);
        return result;
    },

    _setDisabledAttr: function(value) {
        dojo.forEach(this.getChildren(), function(child) {
            child.attr('disabled', value);
        });
    },
});

        