dojo.provide('unc.FormGenerator');

dojo.require('dijit._Templated');
dojo.require('dijit._Widget');
dojo.require('dijit._Container');

dojo.require('dijit.form.Form');
dojo.require('dijit.form.Textarea');
dojo.require('dijit.form.Button');
dojo.require('dijit.form.NumberSpinner');
dojo.require('dijit.form.NumberTextBox');
dojo.require('dijit.form.Select');
dojo.require('dijit.Editor');
dojo.require('dijit.Tooltip');

dojo.declare('unc.FormGenerator', [ dijit.form.Form ], {
    schema: {}, // object describing the JSON schema for the object this form is to edit,
    initValue: {}, // object giving the initial value for the object

    /**
     * Called to initialize the FormGenerator. The content is generated and linked into the DOM.
     */
    postCreate: function() {
        this.inherited(arguments);

        var w = this.generate('formContent', this.schema, this.initValue);
        dojo.addClass(this.containerNode, 'uncFormGenerator');
        dojo.place(w.domNode, this.containerNode);
    },

    /**
     * Generate controls for the given schema initialized with value, called recursively
     */
    generate: function(name, schema, value) {
        // determine the method to call by introspection
        var type = schema.type;
        var method = 'generate_' + type;
        if (method in this) {
            return this[method](name, schema, value);
        } else {
            console.log('FormGenerator: no method', method);
        }
    },

    /**
     * Generate fieldset for an object schema
     */
    generate_object: function(name, schema, value) {
        var title = schema.title || name;
        var manager = new unc.ObjectManager({
            name: name,
            theTitle: title,
            description: schema.description || ''
        });

        for(var propertyName in schema.properties) {
            var propertySchema = schema.properties[propertyName];
            var propertyValue = null;
            if (value && value[propertyName] !== undefined) {
                propertyValue = value[propertyName];
            }
            manager.addChild(this.generate(propertyName, propertySchema, propertyValue));
        }
        return manager;
    },

    /**
     * Generate a string input control
     */
    generate_string: function(name, schema, value) {
        var title = schema.title || name;
        var format = schema.format || 'text';
        var init = value || schema['default'] || '';
        var description = schema.description || '';
        var control;
        if (format == 'html') {
            control = new dijit.Editor({
                name: name,
                value: init
            });
        } else {
            if ('enum' in schema) {
                var options = dojo.map(schema['enum'], function(e, i) {
                    return { 
                        value: e,
                        label: e,
                        selected: i === 0,
                        disabled: false
                    };
                });
                control = new dijit.form.Select({
                    name: name,
                    value: init,
                    options: options
                });
            } else {
                control = new dijit.form.Textarea({
                    name: name,
                    value: init,
                    readOnly: 'readonly' in schema && schema['readonly'],
                    baseClass: 'dijitTextBox dijitTextArea' // why do I need this?
                });
            }
        }
        this.connect(control, 'onChange', 'onChange');
        var manager = new unc.FieldManager({
            theTitle: title,
            control: control,
            description: description
        });
        return manager;
    },

    /**
     * Generate an integer input control
     */
    generate_integer: function(name, schema, value) {
        var title = schema.title || name;
        var format = schema.format || 'text';
        var init = value || schema['default'] || 0;
        var constraints = {places: 0};
        var description = schema.description || '';
        if ("minimum" in schema) {
            constraints.min = schema.minimum;
        }
        if ("maximum" in schema) {
            constraints.max = schema.maximum;
        }
        var control = new dijit.form.NumberSpinner({
            name: name,
            value: init,
            constraints: constraints
        });
        this.connect(control, 'onChange', 'onChange');
        manager = new unc.FieldManager({
            theTitle: title,
            control: control,
            description: description
        });
        return manager;
    },

    /**
     * Generate a number input control
     */
    generate_number: function(name, schema, value) {
        var title = schema.title || name;
        var format = schema.format || 'text';
        var init = value || schema['default'] || 0;
        var constraints = { };
        var description = schema.description || '';
        if ("minimum" in schema) {
            constraints.min = schema.minimum;
        }
        if ("maximum" in schema) {
            constraints.max = schema.maximum;
        }
        var control = new dijit.form.NumberSpinner({
            name: name,
            value: init,
            constraints: constraints
        });
        this.connect(control, 'onChange', 'onChange');
        manager = new unc.FieldManager({
            theTitle: title,
            control: control,
            description: description
        });
        return manager;
    },

    /**
     * Generate an array manager
     */
    generate_array: function(name, schema, value) {
        var title = schema.title || name;
        var init = value || schema['default'] || [];
        var description = schema.description || "";
        var manager = new unc.ArrayManager({
            name: name,
            theTitle: title,
            description: description
        });
        // create an empty model item
        var item = this.generate(title, schema.items, null);
        // insert its add button
        var button = dojo.create('img', {src: "images/add.png", width: "16", height: "16",
            title: "Click to add a new " + title + "." }, item.arrayControl);
        this.connect(button, 'onclick', function() {
            var item = this.generate(title, schema.items, null);
            manager.addItem(item);
        });
        // the model is disabled
        item.attr('disabled', true);
        // insert it into the manager
        manager.addChild(item);

        // now generate the real nodes
        for (var i=0; i < init.length; i++) {
            item = this.generate(title, schema.items, init[i]);
            manager.addItem(item);
        }
        return manager;
    },

    /**
     * Return the value of the object represented by the form
     */
    _getValueAttr: function() {
        var children = this.getChildren();
        var result = dojo.map(children, function(child) { return child.attr('value'); });
        // I expect only one child here at the top level
        if (result.length == 1) {
            result = result[0];
        }
        return result;
    },
    
    /**
     * Signal any of the contained controls changing value
     */
     onChange: function() {
     },

});

dojo.declare('unc.ArrayManager', [ dijit._Widget, dijit._Templated, dijit._Container ], {
    templatePath: dojo.moduleUrl("unc", "ArrayManager.html"),
    widgetsInTemplate: true,

    name: "",
    theTitle: "",
    description: "",

    /**
     * Add an item to the array and decorate it with the array controls
     */
    addItem: function(item) {
        var children = this.getChildren();
        var N = children.length;
        var button = dojo.create('img', {src: "images/cross.png", width: "16", height: "16",
            title: "Click to delete this item." }, item.arrayControl);
        this.connect(button, 'onclick', function() {
            item.destroyRecursive();
            this.renumber();
        });
        dojo.place(item.domNode, children[N-1].domNode, 'before');
        item.arrayIndex.innerHTML = N;
        children[N-1].arrayIndex.innerHTML = N+1;
    },

    /**
     * Renumber the array items after a delete or other reorganization
     */
    renumber: function(item) {
        dojo.forEach(this.getChildren(), function(item, index) {
            item.arrayIndex.innerHTML = index+1;
        });
    },

    /**
     * Return the value of the array
     */
    _getValueAttr: function() {
        var children = this.getChildren();
        children.pop(); // the last one is the dummy example
        var result = dojo.map(children, function(child) { return child.attr('value'); }, this);
        return result;
    }

});

dojo.declare('unc.ObjectManager', [ dijit._Widget, dijit._Templated, dijit._Container ], {
    templatePath: dojo.moduleUrl("unc", "ObjectManager.html"),
    widgetsInTemplate: true,

    name: "",
    theTitle: "",
    description: "",

    /**
     * Return the object's value
     */
    _getValueAttr: function() {
        var children = this.getChildren();
        var result = {};
        dojo.forEach(children, function(child) {
            result[child.name] = child.attr('value');
        }, this);
        return result;
    },

    /**
     * Set the disabled attribute for all the children
     */
    _setDisabledAttr: function(value) {
        dojo.forEach(this.getChildren(), function(child) {
            child.attr('disabled', value);
        });
    }
});

dojo.declare('unc.FieldManager', [ dijit._Widget, dijit._Templated, dijit._Container ], {
    templatePath: dojo.moduleUrl("unc", "FieldManager.html"),
    widgetsInTemplate: true,

    control: null,
    name: "",
    theTitle: "",
    description: "",

    /**
     * Initialize the widget and connect up the tooltip
     */
    postCreate: function() {
        this.inherited(arguments);
        dojo.place(this.control.domNode, this.containerNode);
        this.name = this.control.name;
        if (this.description) {
            var tt = new dijit.Tooltip({
                connectId: [ this.control.domNode ], 
                label: this.description});
        }
    },

    /**
     * Return the value of the enclosed control
     */
    _getValueAttr: function() {
        return this.control.attr('value');
    },

    /**
     * Set the disabled attribute of the enclosed control
     */
    _setDisabledAttr: function(value) {
        this.control.attr('disabled', value);
    }
});
