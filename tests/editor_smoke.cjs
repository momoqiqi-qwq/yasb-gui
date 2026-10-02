// Exercise the WebView bridge without a browser or external Node dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '../app/core/editor/code_editor.html'), 'utf8');
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)][0][1];
const messages = [], commands = [], undo = [];
let value = '', stops = 0;
const editorOptions = {fontFamily: 'Test Font', fontSize: 18};
const modelOptions = {};
const model = {
    updateOptions: options => Object.assign(modelOptions, options),
    getFullModelRange: () => ({startLineNumber: 1, endLineNumber: 1}),
};
const editor = {
    updateOptions: options => Object.assign(editorOptions, options),
    getModel: () => model,
    setValue: content => { value = content; },
    getValue: () => value,
    pushUndoStop: () => stops++,
    executeEdits: (source, edits) => { undo.push(value); value = edits[0].text; },
    getPosition: () => ({lineNumber: 1, column: 1}),
    setPosition: () => {}, focus: () => {},
    addCommand: (key, callback) => commands.push(callback),
    onDidChangeModelContent: () => {}, onDidPaste: () => {},
};
const document = {
    getElementById: () => ({classList: {add() {}, remove() {}}}),
    createElement: () => ({}), head: {appendChild() {}}, body: {},
};
const loader = (deps, callback) => callback();
loader.config = () => {};
const context = vm.createContext({
    URLSearchParams, require: loader, document, console, setTimeout: callback => callback(),
    monaco: {
        editor: {defineTheme() {}, create: () => editor, setModelMarkers() {}, setModelLanguage() {}, setTheme() {}},
        languages: {css: {cssDefaults: {setModeConfiguration() {}}}},
        KeyMod: {CtrlCmd: 1}, KeyCode: {KeyS: 2},
    },
    window: {
        location: {href: 'file:///editor.html', search: ''},
        chrome: {webview: {postMessage: message => messages.push(message), addEventListener() {}}},
    },
});
vm.runInContext(script, context);
assert.equal(context.window.editor, editor, 'Native menu must access the initialized editor');
vm.runInContext('setFont(null, 22)', context);
assert.equal(editorOptions.fontFamily, 'Test Font', 'Changing size must keep the font');
vm.runInContext('setFont("Another Font", null)', context);
assert.equal(editorOptions.fontSize, 22, 'Changing font must keep the size');
vm.runInContext('setLanguage("css"); setEditorOptions({tabSize:4, wordWrap:"off"})', context);
assert.equal(modelOptions.tabSize, 4);
vm.runInContext('setLanguage("yaml"); setEditorOptions({tabSize:8})', context);
assert.equal(modelOptions.tabSize, 2, 'YAML indentation must remain valid');
value = '.bar { content: "a  b;{}"; }';
vm.runInContext('setFormattedContent("")', context);
assert.equal(value, '', 'Formatting may produce empty content');
assert.equal(undo.pop(), '.bar { content: "a  b;{}"; }', 'Formatting must preserve an undo step');
assert.equal(stops, 2);
vm.runInContext('setLanguage("css")', context);
commands[0]();
assert.equal(messages.at(-1).type, 'save');
assert.equal(messages.at(-1).content, '', 'Ctrl+S must accept empty CSS');
console.log('Editor bridge smoke checks passed');
