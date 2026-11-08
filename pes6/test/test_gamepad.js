// Node 18+ static regression test for the Android TV gamepad shim.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let native = [], events = [];
const context = {
  window: {dispatchEvent(e){events.push(e.type)}},
  navigator: {getGamepads(){return native}},
  performance: {now(){return 3}},
  Event: class Event {constructor(type){this.type=type}},
  Array, Number, Object
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(__dirname+'/../assets/gamepad-bridge.js','utf8'),context);
const bridge = context.window.__pes6PadBridge;
assert.equal(context.navigator.getGamepads().length,0);
bridge.button(0,true);
assert.equal(context.navigator.getGamepads()[0].buttons[0].pressed,true);
assert.deepEqual(events,['gamepadconnected']);
bridge.button(0,false);
assert.equal(context.navigator.getGamepads()[0].buttons[0].pressed,false);
bridge.axes([.2,-.4,.6,-.8],.8,0,-1,-1);
assert.equal(context.navigator.getGamepads()[0].buttons[6].pressed,true);
assert.equal(context.navigator.getGamepads()[0].buttons[12].pressed,true);
assert.equal(context.navigator.getGamepads()[0].buttons[14].pressed,true);
bridge.axes([0,0,0,0],0,0,0,0);
assert.equal(context.navigator.getGamepads()[0].buttons[6].pressed,false);
assert.equal(context.navigator.getGamepads()[0].buttons[12].pressed,false);
assert.equal(context.navigator.getGamepads()[0].buttons[14].pressed,false);
native = [{connected:true,id:'native'}];
assert.equal(context.navigator.getGamepads()[0].id,'native');
console.log('Gamepad shim PASS');
