/* Gamepad API compatibility shim for Android TV WebView.
 * Keeps native gamepads first; emulates standard Gamepad when native enumeration is absent.
 * Receives only physical input events from the Android activity. */
(function () {
  'use strict';
  if (window.__pes6PadBridge) return;
  var nativeGet = typeof navigator.getGamepads === 'function'
    ? navigator.getGamepads.bind(navigator) : null;
  var pad = {
    id: 'Android TV HID controller (PES6 bridge)', index: 0,
    connected: true, mapping: 'standard', timestamp: 0, axes: [0, 0, 0, 0],
    buttons: Array.from({length: 17}, function () {
      return {pressed: false, touched: false, value: 0};
    })
  };
  var active = false, keys = Array(17).fill(false);
  function nativePads() {
    try { return nativeGet ? nativeGet() : []; } catch (e) { return []; }
  }
  function hasPad(pads) {
    return !!pads && Array.prototype.some.call(pads, function (p) {
      return !!(p && p.connected);
    });
  }
  function connect() {
    if (!active) {
      active = true;
      try {
        var event = new Event('gamepadconnected');
        Object.defineProperty(event, 'gamepad', {value: pad});
        window.dispatchEvent(event);
      } catch (e) {}
    }
    pad.timestamp = performance.now();
  }
  var bridge = {
    button: function (i, down) {
      if (!Number.isInteger(i) || i < 0 || i >= 17) return;
      connect(); keys[i] = !!down;
      var b = pad.buttons[i];
      b.pressed = b.touched = keys[i];
      b.value = keys[i] ? 1 : 0;
    },
    axes: function (axes, lt, rt, hx, hy) {
      if (!Array.isArray(axes) || axes.length !== 4) return;
      connect();
      pad.axes = axes.map(function (v) {
        return Math.max(-1, Math.min(1, Number(v) || 0));
      });
      [lt, rt].forEach(function (v, n) {
        var b = pad.buttons[6 + n];
        b.value = Math.max(keys[6 + n] ? 1 : 0, Math.min(1, Math.max(0, Number(v) || 0)));
        b.touched = b.value > .05; b.pressed = b.value > .5;
      });
      [[12, Number(hy) < -.5], [13, Number(hy) > .5],
       [14, Number(hx) < -.5], [15, Number(hx) > .5]].forEach(function (entry) {
        var b = pad.buttons[entry[0]];
        b.pressed = keys[entry[0]] || entry[1];
        b.touched = b.pressed;
        b.value = b.pressed ? 1 : 0;
      });
    }
  };
  Object.defineProperty(window, '__pes6PadBridge', {value: bridge, configurable: true});
  try {
    Object.defineProperty(navigator, 'getGamepads', {
      configurable: true,
      value: function () {
        var pads = nativePads();
        return hasPad(pads) ? pads : (active ? [pad] : pads);
      }
    });
  } catch (e) { /* Browser native API still works. */ }
})();
