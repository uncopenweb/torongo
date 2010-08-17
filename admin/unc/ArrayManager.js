dojo.provide('unc.ArrayManager');

dojo.require('dijit._Templated');
dojo.require('dijit._Widget');
dojo.require('dijit._Container');
dojo.require('dijit.form.Button');

dojo.declare('unc.ArrayManager', [ dijit._Widget, dijit._Templated, dijit._Container ], {
    templatePath: dojo.moduleUrl("unc", "ArrayManager.html"),
    widgetsInTemplate: true,

    generator: null,
    schema: {},
    name: "",
    title: "",
    init: [],
    description: "",

    postCreate: function() {
        this.inherited(arguments);

        //console.log('startup ArrayManager', this.containerNode, this.init);
        var last;
        for(var i=0; i <= this.init.length; i++) {
            last = this.generator(this.title + ' ' + (i+1), this.schema, this.init[i], 
                                  this.containerNode);
            var button;
            if (i == this.init.length) {
                button = new dijit.form.Button({
                    label: 'Add', iconClass: 'addIcon', showLabel: false,
                    onClick: dojo.hitch(this, 'addItem'),
                });
                //this.connect(button, 'onClick', 'addItem');
            } else {
                button = new dijit.form.Button({
                    label: 'Delete', iconClass: 'deleteIcon', showLabel: false,
                    onClick: dojo.hitch(this, 'deleteItem', last),
                });
                //this.connect(button, 'onClick', 'deleteItem');
            }
            if (this.schema.type == 'object' || this.schema.type == 'array') {
                dojo.place(button.domNode, last.itemControl);
            } else {
                dojo.place(button.domNode, this.containerNode);
            }
            dojo.create('br', {clear:'all'}, this.containerNode);
        }
        last.attr('disabled', true);
        this.connect(this.add, 'onClick', 'addItem');
    },

    addItem: function() {
        var children = this.getChildren();
        children[children.length-1].attr('disabled', false);
        var w = this.generator('['+(children.length+1)+']', this.schema, null, this.containerNode);
        w.attr('disabled', true);
    },

    deleteItem: function(item, e) {
        var children = this.getChildren();
        console.log('deleteItem', item, children);
        var i = dojo.indexOf(children, item);
        console.log('i=',i);
    },

    itemClick: function(e) {
        console.log(e);
    },

    _getValueAttr: function() {
        var children = this.getChildren();
        children.pop();
        var result = [];
        dojo.forEach(children, function(child) {
            result.push(child.attr('value'));
        }, this);
        return result;
    }

});

        