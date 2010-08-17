dojo.provide('unc.CollectionEditor');

dojo.require('unc.FormGenerator');
dojo.require('dijit._Templated');
dojo.require('dijit._Widget');
dojo.require('dijit._Container');
dojo.require('dijit.form.Button');
dojo.require('dojox.grid.DataGrid');

dojo.declare('unc.CollectionEditor', [ dijit._Widget, dijit._Templated, dijit._Container ], {
    templatePath: dojo.moduleUrl("unc", "CollectionEditor.html"),
    widgetsInTemplate: true,

    schema: {}, // schema for this collection
    store: {}, // JsonRestStore representing the collection
    gridLayout: {}, // layout for the Grid we'll use to find records

    current: null, // item being edited if it is from the collection
    form: null, // form control if it has been created
    
    postCreate: function() {
        this.inherited(arguments);

        this.grid = new dojox.grid.DataGrid({
            store: this.store,
            structure: this.gridLayout});
        dojo.place(this.grid.domNode, this.gridGoesHere);
        this.connect(this.grid, 'onSelectionChanged', 'checkSelection');
        this.connect(this.grid, 'onRowDblClick', 'editItem');
        this.connect(this.deleteButton, 'onClick', 'deleteItem');
        this.deleteButton.attr('disabled', true);
        this.connect(this.newButton, 'onClick', 'newItem');
        this.connect(this.saveButton, 'onClick', 'save');
        this.saveButton.attr('disabled', true);        
        this.connect(this.saveNewButton, 'onClick', 'saveAsNew');
        this.saveNewButton.attr('disabled', true);
    },

    checkSelection: function() {
        var selected = this.grid.selection.getSelected();
        console.log('cS', selected);
        this.deleteButton.attr('disabled', selected.length == 0);
        this.current = selected[0];
    },

    startup: function() {
        this.inherited(arguments);
        
        this.grid.startup();
    },

    editItem: function(evt) {
        console.log('editItem');
        var row = evt.rowIndex;
        var item = this.grid.getItem(row);
        this.current = item; // remember which we're editing
        if (this.form != null) this.form.destroyRecursive();
        this.form = new unc.FormGenerator({
            schema: this.schema,
            initValue: item });
        dojo.place(this.form.domNode, this.formGoesHere, 'only');
        this.saveButton.attr('disabled', false);
        this.saveNewButton.attr('disabled', false);
        console.log('editItem ends');
    },

    newItem: function(e) {
        this.current = this.store.newItem();
        console.log('current', this.current);
        if (this.form) this.form.destroyRecursive();
        this.form = new unc.FormGenerator({
            schema: this.schema,
            initValue: this.current });
        dojo.place(this.form.domNode, this.formGoesHere, 'only'); 
        this.saveButton.attr('disabled', false);
        this.saveNewButton.attr('disabled', true);
        console.log('new exits');
    },

    save: function() {
        var value = this.form.attr('value');

        this.store.changing(this.current);
        dojo.mixin(this.current, value);
        var a = this.store.save({
            onComplete: function() {
                console.log('save complete, does grid update?');
                // apparently they don't trigger this when changing is used.
                this.store.onSet(this.current);
            },
            scope: this
        });
        console.log('actions=', a);
    },

    saveAsNew: function() {
        delete this.current._id;
        this.save();
    },

    deleteItem: function() {
        this.store.deleteItem(this.current);
        this.store.save();
        this.deleteButton.attr('disabled', true);
    }


});
