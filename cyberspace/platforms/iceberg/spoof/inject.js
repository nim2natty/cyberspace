/* veil anti-fingerprinting injection.
 * Runs in the main world before any page script (via context.add_init_script).
 * Reads config from window.__VEIL__ which Python sets first, then deletes it.
 *
 * Covers: navigator (UA/platform/cores/memory/touch), screen, timezone/Intl,
 * canvas noise, WebGL vendor/renderer, AudioContext noise, WebRTC leak
 * prevention, userAgentData (ClientHints), and automation-flag scrubbing.
 */
(function () {
  "use strict";
  if (window.__VEIL_SPOOFED__) { return; }
  window.__VEIL_SPOOFED__ = true;

  var C = window.__VEIL__ || {};
  var seed = (function (s) {
    var h = 2166136261 >>> 0;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
    return h >>> 0;
  })(C.noise_seed || "veil");

  function rnd() {
    seed = (seed + 0x6D2B79F5) >>> 0;
    var t = seed;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  function defineProp(obj, prop, value) {
    try {
      Object.defineProperty(obj, prop, {
        get: (typeof value === "function") ? value : function () { return value; },
        configurable: true,
      });
    } catch (e) {}
  }

  // ---- Navigator -----------------------------------------------------------
  var nav = navigator;
  defineProp(nav, "userAgent", C.user_agent || nav.userAgent);
  defineProp(nav, "appVersion", (C.user_agent || nav.userAgent).replace("Mozilla/", ""));
  defineProp(nav, "platform", C.platform || nav.platform);
  defineProp(nav, "vendor", /Chrome/.test(C.user_agent || "") ? "Google Inc."
        : /Firefox/.test(C.user_agent || "") ? "" : "Apple Computer, Inc.");
  defineProp(nav, "language", C.locale || nav.language);
  defineProp(nav, "languages", Object.freeze((C.languages || ["en-US", "en"]).slice()));
  defineProp(nav, "hardwareConcurrency", C.hardware_concurrency || 8);
  if (C.device_memory != null) { defineProp(nav, "deviceMemory", C.device_memory); }
  defineProp(nav, "maxTouchPoints", C.max_touch_points != null ? C.max_touch_points : 0);
  defineProp(nav, "webdriver", false);
  defineProp(nav, "doNotTrack", C.block_tracking ? "1" : null);
  defineProp(nav, "pdfViewerEnabled", true);

  // ---- Screen / window -----------------------------------------------------
  var sw = C.screen_width || 1920, sh = C.screen_height || 1080;
  if (window.screen) {
    defineProp(screen, "width", sw);
    defineProp(screen, "height", sh);
    defineProp(screen, "availWidth", sw);
    defineProp(screen, "availHeight", sh - 40);
    defineProp(screen, "colorDepth", C.color_depth || 24);
    defineProp(screen, "pixelDepth", C.color_depth || 24);
  }
  defineProp(window, "devicePixelRatio", C.device_pixel_ratio || 1.0);
  defineProp(window, "outerWidth", sw);
  defineProp(window, "outerHeight", sh);
  // ---- Timezone / Intl / Date --------------------------------------------
  var tz = C.timezone || "America/New_York";
  try {
    var origDTF = Intl.DateTimeFormat;
    Intl.DateTimeFormat = function () {
      var args = Array.prototype.slice.call(arguments);
      if (!args[0] || typeof args[0] === "string") { args[0] = (args[0] && args[0] !== "en-US") ? args[0] : undefined; }
      args[1] = args[1] || {};
      args[1].timeZone = args[1].timeZone || tz;
      return new origDTF(args[0], args[1]);
    };
    Intl.DateTimeFormat.prototype = origDTF.prototype;
    var d = new origDTF("en-US", { timeZone: tz, timeZoneName: "shortOffset" });
    var parts = d.formatToParts(new Date());
    var off = parts.find(function (p) { return p.type === "timeZoneName"; });
    var m = off && off.value.match(/GMT([+-])(\d{1,2}):?(\d{2})?/);
    var mins = 300;
    if (m) { mins = (parseInt(m[2], 10) * 60 + parseInt(m[3] || "0", 10)) * (m[1] === "-" ? 1 : -1); }
    // getTimezoneOffset is a *method* (called as date.getTimezoneOffset()),
    // so it needs a function value, not a getter.
    try {
      Object.defineProperty(Date.prototype, "getTimezoneOffset", {
        value: function () { return mins; },
        configurable: true,
        writable: true,
      });
    } catch (e) {}
  } catch (e) {}

  // ---- Canvas fingerprint noise -------------------------------------------
  if (C.canvas_noise !== false) {
    var toDataURL = HTMLCanvasElement.prototype.toDataURL;
    var toBlob = HTMLCanvasElement.prototype.toBlob;
    var getImageData = CanvasRenderingContext2D.prototype.getImageData;
    function addNoise(canvas) {
      try {
        var ctx = canvas.getContext("2d");
        if (!ctx) { return; }
        var w = canvas.width, h = canvas.height;
        if (w === 0 || h === 0) { return; }
        var img = getImageData.apply(ctx, [0, 0, w, h]);
        var dd = img.data;
        for (var i = 0; i < dd.length; i += 4) {
          // (rnd()*2-1)|0 is always 0 (range (-1,1)); use a real perturbation.
          var n = ((rnd() * 3) | 0) - 1; // -1, 0 or 1
          dd[i] = Math.max(0, Math.min(255, dd[i] + n));
        }
        ctx.putImageData(img, 0, 0);
      } catch (e) {}
    }
    HTMLCanvasElement.prototype.toDataURL = function () { addNoise(this); return toDataURL.apply(this, arguments); };
    HTMLCanvasElement.prototype.toBlob = function () { addNoise(this); return toBlob.apply(this, arguments); };
  }

  // ---- WebGL vendor / renderer --------------------------------------------
  function spoofGetParameter(proto) {
    try {
      var gp = proto.getParameter;
      proto.getParameter = function (p) {
        if (p === 37445) { return C.webgl_vendor || "Google Inc. (Intel)"; }
        if (p === 37446) { return C.webgl_renderer || "ANGLE (Intel)"; }
        return gp.apply(this, arguments);
      };
    } catch (e) {}
  }
  if (window.WebGLRenderingContext) { spoofGetParameter(WebGLRenderingContext.prototype); }
  if (window.WebGL2RenderingContext) { spoofGetParameter(WebGL2RenderingContext.prototype); }
  // ---- AudioContext fingerprint noise -------------------------------------
  if (C.audio_noise !== false) {
    function spoofAudio(Ctor) {
      if (!Ctor) { return; }
      try {
        var orig = Ctor.prototype.createOscillator;
        Ctor.prototype.createOscillator = function () {
          var osc = orig.apply(this, arguments);
          try {
            var gv = rnd() * 0.0000001; // imperceptible gain variance
            var gain = this.createGain();
            if (gain && gain.gain) { gain.gain.value = 1 + gv; }
          } catch (e) {}
          return osc;
        };
      } catch (e) {}
    }
    spoofAudio(window.OfflineAudioContext || window.webkitOfflineAudioContext);
    spoofAudio(window.AudioContext || window.webkitAudioContext);
  }

  // ---- WebRTC leak prevention ("hide me from me") -------------------------
  // proxy_only: never reveal the local interface IP. We neutralise STUN by
  // forcing a single ICE candidate or blocking the connection entirely for
  // host candidates, so the real LAN/exit IP cannot be read.
  if (C.webrtc_mode === "proxy_only" || C.webrtc_mode === "disabled") {
    if (window.RTCPeerConnection) {
      var OrigRTC = window.RTCPeerConnection;
      window.RTCPeerConnection = function (config, constraints) {
        if (config && Array.isArray(config.iceServers)) {
          // strip STUN/TURN that could leak the real public IP
          config.iceServers = [];
        }
        if (!config) { config = {}; }
        config.iceTransportPolicy = "relay"; // only relay candidates (proxy side)
        var pc = new OrigRTC(config, constraints);
        var addIce = pc.addIceCandidate.bind(pc);
        pc.addEventListener("icecandidate", function (e) {
          if (e.candidate && /srflx|host/.test(e.candidate.candidate || "")) {
            e.stopImmediatePropagation();
          }
        });
        return pc;
      };
      window.RTCPeerConnection.prototype = OrigRTC.prototype;
    }
  }

  // ---- userAgentData (ClientHints high-entropy) ---------------------------
  if (C.user_agent && /Chrome/.test(C.user_agent) && navigator.userAgentData) {
    try {
      var brandVer = (function () {
        var m = C.user_agent.match(/Chrome\/(\d+)/);
        return m ? m[1] : "126";
      })();
      var brands = C.sec_ch_ua
        ? C.sec_ch_ua.split(",").map(function (b) {
            var mm = b.trim().match(/^(.*?);v="([^"]+)"$/);
            return mm ? { brand: mm[1], version: mm[2] } : { brand: b.trim(), version: brandVer };
          })
        : [{ brand: "Chromium", version: brandVer }, { brand: "Google Chrome", version: brandVer }];
      var uad = {
        brands: brands,
        mobile: C.sec_ch_ua_mobile === "?1",
        platform: (C.sec_ch_ua_platform || '"Unknown"').replace(/"/g, ""),
      };
      defineProp(navigator, "userAgentData", uad);
      if (navigator.userAgentData && navigator.userAgentData.getHighEntropyValues) {
        navigator.userAgentData.getHighEntropyValues = function () {
          return Promise.resolve({
            architecture: C.architecture || "x86",
            bitness: C.bitness || "64",
            mobile: uad.mobile,
            model: "",
            platform: uad.platform,
            platformVersion: C.platform_version || "0.0.0",
            uaFullVersion: (C.user_agent.match(/Chrome\/([\d.]+)/) || [])[1] || "126.0.0.0",
            fullVersionList: C.ua_full_version_list
              ? C.ua_full_version_list.split(",").map(function (b) {
                  var mm = b.trim().match(/^(.*?);v="([^"]+)"$/);
                  return mm ? { brand: mm[1], version: mm[2] } : null;
                }).filter(Boolean)
              : brands,
          });
        };
      }
    } catch (e) {}
  }

  // ---- Scrub the config so a page cannot read our profile -----------------
  try { delete window.__VEIL__; } catch (e) {}
})();
