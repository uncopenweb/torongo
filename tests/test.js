goodItem = { 'word': 'good',
             'value': 42
           };
badItem = { 'word': 'bad',
            'badkey': 'this is not allowed'
          };

function isOK(mode, letter) {
    return mode.indexOf(letter) >= 0;
}

var combine = function(a) {
    var fn = function(n, src, got, all) {
        if (n === 0) {
            if (got.length > 0) {
                all[all.length] = got;
            }
            return;
        }
        for (var j = 0; j < src.length; j++) {
            fn(n - 1, src.slice(j + 1), got.concat([src[j]]), all);
        }
        return;
    };
    var all = [];
    for (var i=0; i < a.length; i++) {
        fn(i, a, [], all);
    }
    all.push(a);
    return all;
};

function doDrop(then) {
    var def = uow.getDatabase({
        'database': 'test',
        'collection': '*',
        'mode': 'DL'
    });
    def.addCallback(function(db) {
        db.fetch({
            query: { '_id': 'test' },
            onItem: function(item) {
                db.deleteItem(item);
            },
            onComplete: function(items) {
                then();
            },
            onError: function() {
            }
        });
    });
}

function doInit(then) {
    var def = uow.getDatabase({
        'database': 'test',
        'collection': 'test',
        'mode': 'c' });
    def.addCallback(function(db) {
        dojo.forEach(['foo', 'bar', 'fee', 'baa' ], function(n, i) {
            db.newItem({'word': n, 'value': i});
        });
        db.save({
            onComplete: function() {
                then();
            },
            onError: function() {
            }
        });
    });
}

function doTest(description, mode, theTest) {
    test(description, function() {
        stop();
        dojo.xhrGet({
            url: '/data/_test_reset',
            sync: true
        });
            
        var def = uow.getDatabase({
                'database': 'test',
                'collection': 'test',
                'mode': mode
            });
        def.addCallback(theTest);
        def.addErrback(function(data) {
            ok(false, 'open should not have failed');
            start();
        });
    });
}

function validateFetch(description, key, value) {
    test(description, function() {
        stop();
        var def = uow.getDatabase({
                'database': 'test',
                'collection': 'test',
                'mode': 'r'
            });
        def.addCallback(function(db) {
            db.fetch( {
                query: { 'word': key },
                onComplete: function(items) {
                    if (value !== false) {
                        ok(items.length > 0, key + ' should be present');
                        equals(items[0].word, key, 'word is correct');
                        equals(items[0].value, value, 'value is correct');
                        start();
                    } else {
                        ok(items.length === 0, key + ' should not be present');
                        start();
                    }
                },
                onError: function() {
                    ok(false, 'validateFetch should not fail');
                    start();
                }
            } );
        });
        def.addErrback(function(data) {
            ok(false, 'open should not have failed');
            start();
        });
    });
}
    
function Create(mode, valid) {
    return function(db) {
        var pass = isOK(mode, 'c') && valid && loggedIn;
        
        db.newItem(valid ? goodItem : badItem );
        db.save( {
            'onComplete': function() { 
                ok(pass, 'write should succeed');
                start();
            },
            'onError': function() {
                ok(!pass, 'write should fail');
                start();
            }
        } );
    };
}


function Update(mode, valid) {
    return function(db) {
        var pass = isOK(mode, 'u') && valid && loggedIn;
        var fpass = isOK(mode, 'r');
        var src = valid ? goodItem : badItem;
        function onFetchComplete(items, request) {
            // we've got the items, not modify the first
            db.setValue(items[0], 'word', src.word);
            db.setValue(items[0], 'value', src.value);
            db.save( {
                'onComplete': function() {
                    ok(pass, 'update should succeed');
                    start();
                },
                'onError': function() {
                    ok(!pass, 'update should fail');
                    start();
                }
            });
        }
            
        db.fetch({
            query: { 'word': 'foo' }, 
            onComplete: onFetchComplete,
            onError: function() {
                ok(!fpass, 'fetch should fail');
                start();
            }
        });
    };
}

function Read(mode) {
    return function(db) {
        var pass = isOK(mode, 'r');
        
        db.fetch({
            query: { 'word': 'foo' },
            onComplete: function(items) {
                ok(pass && items.length > 0, 'some items should be available');
                start();
            },
            onError: function() {
                ok(!pass, 'fetch should fail');
                start();
            }
        });
    };
}

function fetchIt(db, key, value) {
            db.fetch( {
                query: { 'word': key },
                onComplete: function(items) {
                    if (value !== false) {
                        ok(items.length > 0, key + ' should be present');
                        equals(items[0].word, key, 'word is correct');
                        equals(items[0].value, value, 'value is correct');
                        start();
                    } else {
                        ok(items.length === 0, key + ' should not be present');
                        start();
                    }
                },
                onError: function() {
                    ok(false, 'validateFetch should not fail');
                    start();
                }
            } );
}

function Delete(mode) {
    return function(db) {
        var pass = isOK(mode, 'd') && loggedIn;
        var fpass = isOK(mode, 'r');
        
        function onFetchComplete(items, request) {
            // we've got the items, now delete the first
            db.deleteItem(items[0]);
            db.save( {
                'onComplete': function() {
                    ok(pass, 'delete should succeed');
                    start();
                },
                'onError': function() {
                    ok(!pass, 'delete should fail');
                    start();
                }
            });
        }
            
        db.fetch({
            query: { 'word': 'foo' }, 
            onComplete: onFetchComplete,
            onError: function() {
                ok(!fpass, 'fetch should fail');
                start();
            }
        });
    };
}

function main() {
    var user = uow.getUser();
    var id = user.email;
    loggedIn = id !== null;
    dojo.byId('qunit-header').innerHTML = 'UOW Unit Tests by ' + id;

    var modes = dojo.map(combine(['c' , 'r', 'u', 'd']), function(m) {
        return m.join('');
    });
    // test delete
    dojo.forEach(modes, function(mode) {
        var msg = dojo.replace('Delete with mode {0} loggedIn == {1}', [ mode, loggedIn ]);
        doTest(msg, mode, Delete(mode));
        var permission = isOK(mode, 'd') && isOK(mode, 'r') && loggedIn;
        if (permission) {
            validateFetch('foo should be absent', 'foo', false);
        } else {
            validateFetch('foo should be present', 'foo', 0);
        }
    });
    // test read
    dojo.forEach(modes, function(mode) {
        var msg = dojo.replace('Read with mode {0} loggedIn == {1}', [ mode, loggedIn ]);
        doTest(msg, mode, Read(mode));
    });
    // test create and update
    dojo.forEach(['Create', 'Update'], function(func) {
        dojo.forEach(modes, function(mode) {
            var permission = func == 'Create' && isOK(mode, 'c') && loggedIn ||
                             func == 'Update' && isOK(mode, 'u') && isOK(mode, 'r') && loggedIn;
            var validity = [ true ];
            if (permission) {
                validity.push(false);
            } 
            dojo.forEach(validity, function(valid) {
                var msg = dojo.replace('{0} with mode {1} and {2} data loggedIn == {3}',
                                   [func, mode, valid ? 'valid' : 'invalid', loggedIn ]);
                f = eval(func);
                doTest(msg, mode, f(mode, valid));
                if (permission && valid) {
                    validateFetch('good should be present', 'good', goodItem.value);
                } else {
                    validateFetch('bad should be absent', 'bad', false);
                }
            });
        });
    });
}

dojo.ready(main);


