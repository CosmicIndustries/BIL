// ==UserScript==
// @name         Cosmic OTF YouTube
// @namespace    CosmicIndustries
// @version      0.4.0
// @description  Real-time GPU video reconstruction and AudioWorklet DSP for YouTube.
// @author       CosmicIndustries
// @license      MIT
// @match        https://*.youtube.*/*
// @match        https://youtube.*/*
// @match        https://m.youtube.*/*
// @run-at       document-start
// @grant        none
// ==/UserScript==

(() => {
    'use strict';

    /*
     * ==========================================================
     * COSMIC OTF YOUTUBE v0.4
     * ==========================================================
     *
     * VIDEO
     * -----
     * YouTube decoded video
     *       ↓
     * WebGL2 texture
     *       ↓
     * Lanczos-2 reconstruction
     *       ↓
     * detail recovery
     *       ↓
     * GPU framebuffer
     *
     * AUDIO
     * -----
     * YouTube decoded PCM
     *       ↓
     * MediaElementAudioSource
     *       ↓
     * AudioWorklet
     *       ├── preamp
     *       ├── 10-band EQ
     *       ├── air
     *       ├── clarity
     *       ├── stereo width
     *       ├── compression
     *       └── true-peak-style limiter
     *       ↓
     * AudioContext destination
     *
     * UI
     * --
     * The control panel is hidden by default so it never gets in
     * the way of normal viewing. It can be summoned three ways:
     *
     *   1. Alt+Shift+O  — toggles the panel open/closed.
     *   2. Alt+Shift+U  — toggles master bypass (processing on/off)
     *                     without opening the panel.
     *   3. A small floating "OTF" launcher pill, always present in
     *      the corner of the page, for anyone who doesn't know the
     *      shortcuts.
     *
     * Inside the panel, a "More options" switch in the header shows
     * or hides the advanced audio controls (compression, limiter
     * ceiling, stereo width) so first-time users see a simple panel
     * by default. Both the panel-open state and the more-options
     * state are persisted to localStorage like everything else.
     *
     * ==========================================================
     */

    const VERSION = '0.4.0';

    // Bump this if the shape of CFG ever changes incompatibly.
    const STORAGE_KEY =
        'cosmic-otf-youtube-v3';

    // Shipped defaults. loadConfig() deep-merges saved settings on
    // top of this, so adding a new field here is enough to migrate
    // existing users forward without a version bump.
    const DEFAULTS = {

        master: true,

        video: {
            enabled: true,
            scale: 2.0,
            sharpness: 0.12,
            recovery: 0.08
        },

        audio: {

            enabled: true,

            preamp: 0,

            eq: {
                b32: 0,
                b80: 0,
                b160: 0,
                b320: 0,
                b640: 0,
                b1200: 0,
                b2400: 0,
                b4800: 0,
                b9600: 0,
                b16000: 0
            },

            air: 0,

            clarity: 0,

            compression: 0,

            limiter: -1,

            stereo: 0
        },

        preset: 'Transparent',

        // Panel chrome state, persisted so it "remembers" how you
        // last left it.
        ui: {
            // Whether the settings panel is currently shown.
            open: false,
            // Whether the "More options" (advanced audio) section
            // is expanded.
            advanced: false
        }
    };

    let CFG = loadConfig();

    const STATE = {

        video: null,

        canvas: null,

        gl: null,

        videoProgram: null,

        videoTexture: null,

        videoBuffer: null,

        videoUniforms: null,

        videoRAF: 0,

        audioContext: null,

        audioSource: null,

        audioWorklet: null,

        audioVideo: null,

        audioFailed: false,

        panel: null,

        // The always-on-screen pill used to open/close the panel
        // without needing to remember a keyboard shortcut.
        launcher: null,

        initialized: false,

        lastVideoWidth: 0,

        lastVideoHeight: 0
    };


    /* ==========================================================
       GENERAL UTILITIES
       ========================================================== */

    function log(...args) {

        console.log(
            '[COSMIC-OTF]',
            ...args
        );
    }


    function warn(...args) {

        console.warn(
            '[COSMIC-OTF]',
            ...args
        );
    }


    // Recursively merges `source` into `target` in place, only
    // descending into plain objects (arrays and primitives are
    // overwritten wholesale). Used to layer saved/preset settings
    // on top of DEFAULTS without losing fields the source omits.
    function deepMerge(target, source) {

        if (
            !source ||
            typeof source !== 'object'
        ) {
            return target;
        }

        for (
            const key of Object.keys(source)
        ) {

            if (
                source[key] &&
                typeof source[key] === 'object' &&
                !Array.isArray(source[key]) &&
                target[key] &&
                typeof target[key] === 'object'
            ) {

                deepMerge(
                    target[key],
                    source[key]
                );

            } else {

                target[key] =
                    source[key];
            }
        }

        return target;
    }


    function loadConfig() {

        try {

            const saved =
                JSON.parse(
                    localStorage.getItem(
                        STORAGE_KEY
                    )
                );

            return deepMerge(
                structuredClone(DEFAULTS),
                saved || {}
            );

        } catch (error) {

            warn(
                'Could not load settings:',
                error
            );

            return structuredClone(
                DEFAULTS
            );
        }
    }


    function saveConfig() {

        try {

            localStorage.setItem(
                STORAGE_KEY,
                JSON.stringify(CFG)
            );

        } catch (error) {

            warn(
                'Could not save settings:',
                error
            );
        }
    }


    function clamp(
        value,
        minimum,
        maximum
    ) {

        return Math.max(
            minimum,
            Math.min(
                maximum,
                value
            )
        );
    }


    // Dotted-path reader/writer over CFG, e.g. getPath('audio.eq.b80').
    // Lets slider markup declare `data-key="audio.eq.b80"` once and
    // have both binding and persistence "just work".
    function getPath(path) {

        return path
            .split('.')
            .reduce(
                (object, key) =>
                    object[key],
                CFG
            );
    }


    function setPath(
        path,
        value
    ) {

        const parts =
            path.split('.');

        const final =
            parts.pop();

        const object =
            parts.reduce(
                (o, key) =>
                    o[key],
                CFG
            );

        object[final] =
            value;
    }


    /* ==========================================================
       PRESETS
       ========================================================== */

    const PRESETS = {

        Transparent: {

            video: {
                scale: 2,
                sharpness: 0.05,
                recovery: 0
            },

            audio: {

                preamp: 0,

                eq: {
                    b32: 0,
                    b80: 0,
                    b160: 0,
                    b320: 0,
                    b640: 0,
                    b1200: 0,
                    b2400: 0,
                    b4800: 0,
                    b9600: 0,
                    b16000: 0
                },

                air: 0,
                clarity: 0,
                compression: 0,
                limiter: -1,
                stereo: 0
            }
        },


        'YouTube Recovery': {

            video: {
                scale: 2,
                sharpness: 0.12,
                recovery: 0.12
            },

            audio: {

                preamp: -1,

                eq: {
                    b32: 0,
                    b80: 0.3,
                    b160: 0.2,
                    b320: 0,
                    b640: 0,
                    b1200: 0,
                    b2400: 0.2,
                    b4800: 0.4,
                    b9600: 0.6,
                    b16000: 0.8
                },

                air: 0.7,
                clarity: 0.10,
                compression: 0.05,
                limiter: -1,
                stereo: 0
            }
        },


        Crisp: {

            video: {
                scale: 2,
                sharpness: 0.20,
                recovery: 0.18
            },

            audio: {

                preamp: -1,

                eq: {
                    b32: 0,
                    b80: 0,
                    b160: 0,
                    b320: 0,
                    b640: 0,
                    b1200: 0.2,
                    b2400: 0.5,
                    b4800: 0.8,
                    b9600: 1.0,
                    b16000: 1.2
                },

                air: 1.0,
                clarity: 0.20,
                compression: 0,
                limiter: -1,
                stereo: 0
            }
        },


        Warm: {

            video: {
                scale: 2,
                sharpness: 0.08,
                recovery: 0.03
            },

            audio: {

                preamp: -1,

                eq: {
                    b32: 0.5,
                    b80: 1,
                    b160: 0.7,
                    b320: 0.4,
                    b640: 0,
                    b1200: -0.2,
                    b2400: -0.2,
                    b4800: -0.2,
                    b9600: -0.1,
                    b16000: 0
                },

                air: 0,
                clarity: 0,
                compression: 0.08,
                limiter: -1,
                stereo: 0
            }
        },


        Voice: {

            video: {
                scale: 2,
                sharpness: 0.08,
                recovery: 0.03
            },

            audio: {

                preamp: -1,

                eq: {
                    b32: -1,
                    b80: -0.5,
                    b160: -0.2,
                    b320: 0,
                    b640: 0.5,
                    b1200: 1,
                    b2400: 1.5,
                    b4800: 1.2,
                    b9600: 0.5,
                    b16000: 0
                },

                air: 0.2,
                clarity: 0.20,
                compression: 0.15,
                limiter: -1,
                stereo: 0
            }
        },


        Bass: {

            video: {
                scale: 2,
                sharpness: 0.10,
                recovery: 0.05
            },

            audio: {

                preamp: -2,

                eq: {
                    b32: 1,
                    b80: 2,
                    b160: 1.5,
                    b320: 0.5,
                    b640: 0,
                    b1200: 0,
                    b2400: 0,
                    b4800: 0,
                    b9600: 0,
                    b16000: 0
                },

                air: 0,
                clarity: 0,
                compression: 0.15,
                limiter: -1,
                stereo: 0
            }
        }
    };


    function applyPreset(name) {

        const preset =
            PRESETS[name];

        if (!preset)
            return;

        CFG.video =
            deepMerge(
                structuredClone(
                    DEFAULTS.video
                ),
                preset.video
            );

        CFG.audio =
            deepMerge(
                structuredClone(
                    DEFAULTS.audio
                ),
                preset.audio
            );

        CFG.preset =
            name;

        saveConfig();

        sendAudioConfig();

        resizeVideo();

        refreshGUI();
    }


    /* ==========================================================
       AUDIOWORKLET
       ========================================================== */

    // This whole processor is shipped as a string and compiled into
    // a Blob URL at runtime, because AudioWorklet modules must be
    // loaded from a URL — they cannot be registered from an inline
    // function the way a normal ScriptProcessorNode callback can.
    const AUDIO_WORKLET_CODE = `

class Biquad {

    constructor() {

        this.b0 = 1;
        this.b1 = 0;
        this.b2 = 0;

        this.a1 = 0;
        this.a2 = 0;

        this.x1 = 0;
        this.x2 = 0;

        this.y1 = 0;
        this.y2 = 0;
    }

    setCoefficients(c) {

        this.b0 = c.b0;
        this.b1 = c.b1;
        this.b2 = c.b2;

        this.a1 = c.a1;
        this.a2 = c.a2;
    }

    reset() {

        this.x1 = 0;
        this.x2 = 0;

        this.y1 = 0;
        this.y2 = 0;
    }

    // Direct Form I transposed biquad: y[n] = b0*x[n] + b1*x[n-1] +
    // b2*x[n-2] - a1*y[n-1] - a2*y[n-2].
    process(x) {

        const y =
            this.b0 * x +
            this.b1 * this.x1 +
            this.b2 * this.x2 -
            this.a1 * this.y1 -
            this.a2 * this.y2;

        this.x2 =
            this.x1;

        this.x1 =
            x;

        this.y2 =
            this.y1;

        this.y1 =
            y;

        return y;
    }
}


// Divides every coefficient by a0 so the biquad's own a0 is
// implicitly 1, matching the form Biquad.process() expects.
function normalize(
    b0,
    b1,
    b2,
    a0,
    a1,
    a2
) {

    return {

        b0: b0 / a0,
        b1: b1 / a0,
        b2: b2 / a0,

        a1: a1 / a0,
        a2: a2 / a0
    };
}


// RBJ Audio EQ Cookbook peaking filter.
function peaking(
    frequency,
    gainDB,
    Q,
    sampleRate
) {

    const A =
        Math.pow(
            10,
            gainDB / 40
        );

    const w0 =
        2 *
        Math.PI *
        frequency /
        sampleRate;

    const alpha =
        Math.sin(w0) /
        (2 * Q);

    const c =
        Math.cos(w0);

    return normalize(

        1 +
        alpha * A,

        -2 * c,

        1 -
        alpha * A,

        1 +
        alpha / A,

        -2 * c,

        1 -
        alpha / A
    );
}


// RBJ Audio EQ Cookbook low shelf, S=1 (one octave of slope room).
function lowshelf(
    frequency,
    gainDB,
    sampleRate
) {

    const A =
        Math.pow(
            10,
            gainDB / 40
        );

    const w0 =
        2 *
        Math.PI *
        frequency /
        sampleRate;

    const c =
        Math.cos(w0);

    const s =
        Math.sin(w0);

    const alpha =
        s / 2 *
        Math.sqrt(2);

    const beta =
        2 *
        Math.sqrt(A) *
        alpha;

    return normalize(

        A * (
            (A + 1) -
            (A - 1) * c +
            beta
        ),

        2 * A * (
            (A - 1) -
            (A + 1) * c
        ),

        A * (
            (A + 1) -
            (A - 1) * c -
            beta
        ),

        (A + 1) +
        (A - 1) * c +
        beta,

        -2 * (
            (A - 1) +
            (A + 1) * c
        ),

        (A + 1) +
        (A - 1) * c -
        beta
    );
}


// RBJ Audio EQ Cookbook high shelf, S=1.
function highshelf(
    frequency,
    gainDB,
    sampleRate
) {

    const A =
        Math.pow(
            10,
            gainDB / 40
        );

    const w0 =
        2 *
        Math.PI *
        frequency /
        sampleRate;

    const c =
        Math.cos(w0);

    const s =
        Math.sin(w0);

    const alpha =
        s / 2 *
        Math.sqrt(2);

    const beta =
        2 *
        Math.sqrt(A) *
        alpha;

    return normalize(

        A * (
            (A + 1) +
            (A - 1) * c +
            beta
        ),

        -2 * A * (
            (A - 1) +
            (A + 1) * c
        ),

        A * (
            (A + 1) +
            (A - 1) * c -
            beta
        ),

        (A + 1) -
        (A - 1) * c +
        beta,

        2 * (
            (A - 1) -
            (A + 1) * c
        ),

        (A + 1) -
        (A - 1) * c -
        beta
    );
}


class CosmicOTFProcessor
extends AudioWorkletProcessor {

    constructor() {

        super();

        this.enabled =
            true;

        this.preamp =
            0;

        this.eq =
            new Array(10).fill(0);

        this.eqL =
            [];

        this.eqR =
            [];

        this.air =
            0;

        this.clarity =
            0;

        this.compression =
            0;

        this.limiter =
            -1;

        this.stereo =
            0;

        this.previousL =
            0;

        this.previousR =
            0;

        this.historyL =
            [0,0,0];

        this.historyR =
            [0,0,0];

        this.limiterGain =
            1;

        this.targetGain =
            1;

        // The main thread posts { type: 'config', config } every
        // time a slider moves, and { type: 'reset' } on demand.
        this.port.onmessage =
            event => {

                const data =
                    event.data;

                if (
                    data &&
                    data.type ===
                    'config'
                ) {

                    this.configure(
                        data.config
                    );
                }

                if (
                    data &&
                    data.type ===
                    'reset'
                ) {

                    this.reset();
                }
            };
    }


    configure(c) {

        this.enabled =
            !!c.enabled;

        this.preamp =
            Number(
                c.preamp || 0
            );

        this.air =
            Number(
                c.air || 0
            );

        this.clarity =
            Number(
                c.clarity || 0
            );

        this.compression =
            Number(
                c.compression || 0
            );

        this.limiter =
            Number(
                c.limiter ?? -1
            );

        this.stereo =
            Number(
                c.stereo || 0
            );

        if (
            Array.isArray(c.eq)
        ) {

            this.eq =
                c.eq
                    .slice(0,10)
                    .map(Number);

            while (
                this.eq.length <
                10
            ) {

                this.eq.push(0);
            }
        }

        // Coefficients are cheap to recompute and only happen on a
        // config message, not per-sample, so no caching needed.
        this.buildEQ();
    }


    buildEQ() {

        const frequencies = [
            32,
            80,
            160,
            320,
            640,
            1200,
            2400,
            4800,
            9600,
            16000
        ];

        this.eqL = [];
        this.eqR = [];

        for (
            let i = 0;
            i < 10;
            i++
        ) {

            let coefficients;

            // End bands act as shelves so gain extends to DC / Nyquist
            // instead of rolling back off past the band's peak.
            if (i === 0) {

                coefficients =
                    lowshelf(
                        frequencies[i],
                        this.eq[i],
                        sampleRate
                    );

            } else if (
                i === 9
            ) {

                coefficients =
                    highshelf(
                        frequencies[i],
                        this.eq[i],
                        sampleRate
                    );

            } else {

                coefficients =
                    peaking(
                        frequencies[i],
                        this.eq[i],
                        1.0,
                        sampleRate
                    );
            }

            const left =
                new Biquad();

            const right =
                new Biquad();

            left.setCoefficients(
                coefficients
            );

            right.setCoefficients(
                coefficients
            );

            this.eqL.push(left);
            this.eqR.push(right);
        }
    }


    processEQ(
        value,
        chain
    ) {

        let output =
            value;

        for (
            let i = 0;
            i < chain.length;
            i++
        ) {

            output =
                chain[i]
                    .process(output);
        }

        return output;
    }


    // Soft-knee-ish downward compressor: anything past the threshold
    // has its excess divided by a ratio derived from the "amount"
    // slider, instead of being hard-clipped.
    dynamics(value) {

        const amount =
            clamp(
                this.compression,
                0,
                1
            );

        if (
            amount <= 0
        )
            return value;

        const magnitude =
            Math.abs(value);

        const threshold =
            0.707;

        if (
            magnitude <= threshold
        )
            return value;

        const excess =
            magnitude -
            threshold;

        const ratio =
            1 +
            amount * 7;

        const reduced =
            threshold +
            excess / ratio;

        return (
            Math.sign(value) *
            reduced
        );
    }


    // Cubic Hermite (Catmull-Rom) interpolation through 4 control
    // points, used below to approximate what the waveform does
    // *between* samples so the limiter can react to true peaks
    // rather than only sampled peaks.
    hermite(
        y0,
        y1,
        y2,
        y3,
        t
    ) {

        const c0 =
            y1;

        const c1 =
            0.5 *
            (y2 - y0);

        const c2 =
            y0 -
            2.5 * y1 +
            2 * y2 -
            0.5 * y3;

        const c3 =
            0.5 *
            (y3 - y0) +
            1.5 *
            (y1 - y2);

        return (
            (
                (
                    c3 * t +
                    c2
                ) * t +
                c1
            ) * t +
            c0
        );
    }


    // Samples the Hermite curve at several sub-sample positions
    // between p1 and p2 to estimate the true (inter-sample) peak,
    // similar in spirit to ITU-R BS.1770 true-peak metering.
    estimatePeak(
        p0,
        p1,
        p2,
        p3
    ) {

        let peak =
            Math.max(
                Math.abs(p1),
                Math.abs(p2)
            );

        const positions = [
            0.125,
            0.25,
            0.375,
            0.5,
            0.625,
            0.75,
            0.875
        ];

        for (
            const t of positions
        ) {

            const value =
                this.hermite(
                    p0,
                    p1,
                    p2,
                    p3,
                    t
                );

            peak =
                Math.max(
                    peak,
                    Math.abs(value)
                );
        }

        return peak;
    }


    // Asymmetric attack/release gain follower: gain drops fast when
    // a peak exceeds the ceiling and creeps back up slowly, which is
    // what keeps limiting from sounding "pumpy".
    updateLimiter(
        peak
    ) {

        const ceiling =
            Math.pow(
                10,
                this.limiter / 20
            );

        if (
            peak > ceiling
        ) {

            this.targetGain =
                ceiling /
                peak;

        } else {

            this.targetGain =
                1;
        }

        /*
         * Fast attack.
         */
        const attack =
            0.25;

        /*
         * Slower release.
         */
        const release =
            0.004;

        if (
            this.targetGain <
            this.limiterGain
        ) {

            this.limiterGain +=
                (
                    this.targetGain -
                    this.limiterGain
                ) *
                attack;

        } else {

            this.limiterGain +=
                (
                    this.targetGain -
                    this.limiterGain
                ) *
                release;
        }

        return this.limiterGain;
    }


    process(
        inputs,
        outputs
    ) {

        const input =
            inputs[0];

        const output =
            outputs[0];

        if (
            !input ||
            !input.length
        )
            return true;

        const left =
            input[0];

        const right =
            input.length > 1
                ? input[1]
                : input[0];

        const outLeft =
            output[0];

        const outRight =
            output.length > 1
                ? output[1]
                : output[0];

        const preampGain =
            Math.pow(
                10,
                this.preamp / 20
            );

        const ceiling =
            Math.pow(
                10,
                this.limiter / 20
            );

        for (
            let i = 0;
            i < left.length;
            i++
        ) {

            if (!this.enabled) {

                outLeft[i] =
                    left[i];

                if (
                    output.length > 1
                ) {

                    outRight[i] =
                        right[i];
                }

                continue;
            }

            let L =
                left[i] *
                preampGain;

            let R =
                right[i] *
                preampGain;


            /*
             * Parametric EQ.
             */
            L =
                this.processEQ(
                    L,
                    this.eqL
                );

            R =
                this.processEQ(
                    R,
                    this.eqR
                );


            /*
             * Air control.
             *
             * The 16 kHz shelf is already part of the EQ.
             * This additional value provides a small
             * perceptual high-frequency tilt.
             */
            if (
                this.air !== 0
            ) {

                const airGain =
                    Math.pow(
                        10,
                        this.air / 20
                    );

                L *=
                    airGain;

                R *=
                    airGain;
            }


            /*
             * Clarity.
             *
             * A one-pole high-pass (current sample minus the
             * previous output) isolates transient/high-frequency
             * content, which is then added back in to taste.
             */
            if (
                this.clarity > 0
            ) {

                const hpL =
                    L -
                    this.previousL;

                const hpR =
                    R -
                    this.previousR;

                const amount =
                    this.clarity *
                    0.06;

                L +=
                    hpL *
                    amount;

                R +=
                    hpR *
                    amount;

                this.previousL =
                    L;

                this.previousR =
                    R;
            }


            /*
             * Stereo width.
             *
             * Mid/side rebalancing: widen or narrow the side signal
             * relative to mid without touching the mono content.
             */
            if (
                this.stereo !== 0
            ) {

                const mid =
                    (L + R) *
                    0.5;

                const side =
                    (L - R) *
                    0.5;

                const width =
                    1 +
                    this.stereo;

                L =
                    mid +
                    side * width;

                R =
                    mid -
                    side * width;
            }


            /*
             * Compression.
             */
            L =
                this.dynamics(L);

            R =
                this.dynamics(R);


            /*
             * Build four-point history.
             */
            const peakL =
                this.estimatePeak(
                    this.historyL[0],
                    this.historyL[1],
                    this.historyL[2],
                    L
                );

            const peakR =
                this.estimatePeak(
                    this.historyR[0],
                    this.historyR[1],
                    this.historyR[2],
                    R
                );

            const peak =
                Math.max(
                    peakL,
                    peakR
                );


            /*
             * True-peak-style gain control.
             */
            const gain =
                this.updateLimiter(
                    peak
                );

            L *=
                gain;

            R *=
                gain;


            /*
             * Final safety ceiling. The limiter's gain follower can
             * lag by a sample or two, so this clamp is the hard
             * backstop that guarantees output never exceeds ceiling.
             */
            L =
                clamp(
                    L,
                    -ceiling,
                    ceiling
                );

            R =
                clamp(
                    R,
                    -ceiling,
                    ceiling
                );


            outLeft[i] =
                L;

            if (
                output.length > 1
            ) {

                outRight[i] =
                    R;
            }


            /*
             * History.
             */
            this.historyL[0] =
                this.historyL[1];

            this.historyL[1] =
                this.historyL[2];

            this.historyL[2] =
                L;

            this.historyR[0] =
                this.historyR[1];

            this.historyR[1] =
                this.historyR[2];

            this.historyR[2] =
                R;
        }

        return true;
    }
}


registerProcessor(
    'cosmic-otf-dsp',
    CosmicOTFProcessor
);

`;


    /* ==========================================================
       AUDIO INITIALIZATION
       ========================================================== */

    async function initializeAudio(
        video
    ) {

        if (
            !video ||
            STATE.audioVideo === video
        ) {

            return;
        }

        /*
         * A MediaElementAudioSourceNode is tied to its
         * particular HTMLMediaElement.
         */
        if (
            STATE.audioContext
        ) {

            try {

                await STATE.audioContext.close();

            } catch {}

            STATE.audioContext =
                null;

            STATE.audioSource =
                null;

            STATE.audioWorklet =
                null;
        }

        try {

            const AudioContext =
                window.AudioContext ||
                window.webkitAudioContext;

            if (!AudioContext)
                throw new Error(
                    'Web Audio API unavailable'
                );

            const context =
                new AudioContext({
                    latencyHint:
                        'interactive'
                });

            // AudioWorklet modules must be fetched from a URL, so the
            // processor source is wrapped in a Blob and loaded from
            // an object URL that's revoked immediately afterward.
            const blob =
                new Blob(
                    [
                        AUDIO_WORKLET_CODE
                    ],
                    {
                        type:
                            'application/javascript'
                    }
                );

            const url =
                URL.createObjectURL(
                    blob
                );

            try {

                await context.audioWorklet
                    .addModule(url);

            } finally {

                URL.revokeObjectURL(
                    url
                );
            }

            const source =
                context.createMediaElementSource(
                    video
                );

            const worklet =
                new AudioWorkletNode(
                    context,
                    'cosmic-otf-dsp',
                    {
                        numberOfInputs: 1,
                        numberOfOutputs: 1,
                        channelCount: 2,
                        channelCountMode:
                            'clamped-max',
                        channelInterpretation:
                            'speakers'
                    }
                );

            source.connect(
                worklet
            );

            worklet.connect(
                context.destination
            );

            STATE.audioContext =
                context;

            STATE.audioSource =
                source;

            STATE.audioWorklet =
                worklet;

            STATE.audioVideo =
                video;

            STATE.audioFailed =
                false;

            sendAudioConfig();

            /*
             * Browser autoplay policies may initially suspend
             * the context. User interaction will resume it.
             */
            if (
                context.state ===
                'suspended'
            ) {

                try {
                    await context.resume();
                } catch {}
            }

            log(
                'Audio initialized:',
                context.sampleRate,
                'Hz'
            );

        } catch (error) {

            STATE.audioFailed =
                true;

            console.error(
                '[COSMIC-OTF] Audio initialization failed:',
                error
            );
        }
    }


    function sendAudioConfig() {

        if (
            !STATE.audioWorklet
        )
            return;

        const audio =
            CFG.audio;

        STATE.audioWorklet
            .port
            .postMessage({

                type:
                    'config',

                config: {

                    enabled:
                        CFG.master &&
                        audio.enabled,

                    preamp:
                        audio.preamp,

                    eq: [

                        audio.eq.b32,
                        audio.eq.b80,
                        audio.eq.b160,
                        audio.eq.b320,
                        audio.eq.b640,
                        audio.eq.b1200,
                        audio.eq.b2400,
                        audio.eq.b4800,
                        audio.eq.b9600,
                        audio.eq.b16000
                    ],

                    air:
                        audio.air,

                    clarity:
                        audio.clarity,

                    compression:
                        audio.compression,

                    limiter:
                        audio.limiter,

                    stereo:
                        audio.stereo
                }
            });
    }


    /* ==========================================================
       WEBGL VIDEO
       ========================================================== */

    const VIDEO_VERTEX =
`
#version 300 es

in vec2 a_position;

out vec2 v_uv;

void main() {

    v_uv =
        a_position * 0.5 +
        0.5;

    gl_Position =
        vec4(
            a_position,
            0.0,
            1.0
        );
}
`;


    const VIDEO_FRAGMENT =
`
#version 300 es

precision highp float;

uniform sampler2D u_video;

uniform vec2 u_sourceSize;

uniform float u_sharpness;

uniform float u_recovery;

in vec2 v_uv;

out vec4 outColor;

const float PI =
    3.141592653589793;


float sinc(
    float x
) {

    x =
        abs(x);

    if (
        x < 0.00001
    )
        return 1.0;

    x *= PI;

    return (
        sin(x) /
        x
    );
}


// Lanczos-2 kernel: a windowed sinc, zero outside [-2, 2], used as
// the resampling filter for upscaling below.
float lanczos2(
    float x
) {

    x =
        abs(x);

    if (
        x >= 2.0
    )
        return 0.0;

    return
        sinc(x) *
        sinc(x * 0.5);
}


// Reconstructs one output pixel by sampling a 4x4 neighborhood of
// source texels and weighting each by the separable Lanczos-2
// kernel — sharper than bilinear/bicubic without the ringing of
// wider Lanczos windows.
vec3 reconstruct(
    vec2 uv
) {

    vec2 texel =
        1.0 /
        u_sourceSize;

    vec2 source =
        uv *
        u_sourceSize -
        0.5;

    vec2 base =
        floor(source);

    vec2 fraction =
        source -
        base;

    vec3 result =
        vec3(0.0);

    float weightSum =
        0.0;

    for (
        int y = -1;
        y <= 2;
        y++
    ) {

        float wy =
            lanczos2(
                float(y) -
                fraction.y
            );

        for (
            int x = -1;
            x <= 2;
            x++
        ) {

            float wx =
                lanczos2(
                    float(x) -
                    fraction.x
                );

            float weight =
                wx * wy;

            vec2 sampleUV =
                (
                    base +
                    vec2(
                        float(x),
                        float(y)
                    ) +
                    0.5
                ) *
                texel;

            sampleUV =
                clamp(
                    sampleUV,
                    vec2(0.0),
                    vec2(1.0)
                );

            result +=
                texture(
                    u_video,
                    sampleUV
                ).rgb *
                weight;

            weightSum +=
                weight;
        }
    }

    return
        result /
        max(
            weightSum,
            0.00001
        );
}


void main() {

    vec2 texel =
        1.0 /
        u_sourceSize;

    vec3 center =
        reconstruct(v_uv);


    // Unsharp-mask style detail recovery: compare the reconstructed
    // pixel to a cheap 4-neighbor blur of itself, then push the
    // difference (the "detail") back in twice — once as general
    // sharpening, once scaled down as a softer "recovery" pass to
    // fight YouTube's own compression blur.
    vec3 north =
        texture(
            u_video,
            clamp(
                v_uv +
                vec2(
                    0.0,
                    -texel.y
                ),
                vec2(0.0),
                vec2(1.0)
            )
        ).rgb;


    vec3 south =
        texture(
            u_video,
            clamp(
                v_uv +
                vec2(
                    0.0,
                    texel.y
                ),
                vec2(0.0),
                vec2(1.0)
            )
        ).rgb;


    vec3 east =
        texture(
            u_video,
            clamp(
                v_uv +
                vec2(
                    texel.x,
                    0.0
                ),
                vec2(0.0),
                vec2(1.0)
            )
        ).rgb;


    vec3 west =
        texture(
            u_video,
            clamp(
                v_uv -
                vec2(
                    texel.x,
                    0.0
                ),
                vec2(0.0),
                vec2(1.0)
            )
        ).rgb;


    vec3 localAverage =
        (
            north +
            south +
            east +
            west
        ) *
        0.25;


    vec3 detail =
        center -
        localAverage;


    center +=
        detail *
        u_sharpness;


    center +=
        detail *
        u_recovery *
        0.35;


    center =
        clamp(
            center,
            0.0,
            1.0
        );


    outColor =
        vec4(
            center,
            1.0
        );
}
`;


    function compileShader(
        gl,
        type,
        source
    ) {

        const shader =
            gl.createShader(
                type
            );

        gl.shaderSource(
            shader,
            source
        );

        gl.compileShader(
            shader
        );

        if (
            !gl.getShaderParameter(
                shader,
                gl.COMPILE_STATUS
            )
        ) {

            const message =
                gl.getShaderInfoLog(
                    shader
                );

            gl.deleteShader(
                shader
            );

            throw new Error(
                message
            );
        }

        return shader;
    }


    function createVideoProgram(
        gl
    ) {

        const vertex =
            compileShader(
                gl,
                gl.VERTEX_SHADER,
                VIDEO_VERTEX
            );

        const fragment =
            compileShader(
                gl,
                gl.FRAGMENT_SHADER,
                VIDEO_FRAGMENT
            );

        const program =
            gl.createProgram();

        gl.attachShader(
            program,
            vertex
        );

        gl.attachShader(
            program,
            fragment
        );

        gl.linkProgram(
            program
        );

        if (
            !gl.getProgramParameter(
                program,
                gl.LINK_STATUS
            )
        ) {

            throw new Error(
                gl.getProgramInfoLog(
                    program
                )
            );
        }

        gl.deleteShader(
            vertex
        );

        gl.deleteShader(
            fragment
        );

        return program;
    }


    function initializeVideo() {

        if (STATE.gl)
            return true;

        const canvas =
            document.createElement(
                'canvas'
            );

        canvas.id =
            'cosmic-otf-video';

        Object.assign(
            canvas.style,
            {
                position: 'absolute',
                inset: '0',
                width: '100%',
                height: '100%',
                display: 'block',
                zIndex: '30',
                pointerEvents: 'none',
                background: '#000'
            }
        );

        const gl =
            canvas.getContext(
                'webgl2',
                {
                    alpha: false,
                    antialias: false,
                    depth: false,
                    stencil: false,
                    preserveDrawingBuffer:
                        false,
                    powerPreference:
                        'high-performance'
                }
            );

        if (!gl) {

            warn(
                'WebGL2 unavailable'
            );

            return false;
        }

        STATE.canvas =
            canvas;

        STATE.gl =
            gl;

        STATE.videoProgram =
            createVideoProgram(
                gl
            );

        STATE.videoTexture =
            gl.createTexture();

        gl.bindTexture(
            gl.TEXTURE_2D,
            STATE.videoTexture
        );

        gl.texParameteri(
            gl.TEXTURE_2D,
            gl.TEXTURE_MIN_FILTER,
            gl.LINEAR
        );

        gl.texParameteri(
            gl.TEXTURE_2D,
            gl.TEXTURE_MAG_FILTER,
            gl.LINEAR
        );

        gl.texParameteri(
            gl.TEXTURE_2D,
            gl.TEXTURE_WRAP_S,
            gl.CLAMP_TO_EDGE
        );

        gl.texParameteri(
            gl.TEXTURE_2D,
            gl.TEXTURE_WRAP_T,
            gl.CLAMP_TO_EDGE
        );

        STATE.videoBuffer =
            gl.createBuffer();

        gl.bindBuffer(
            gl.ARRAY_BUFFER,
            STATE.videoBuffer
        );

        // A single full-screen quad, drawn as two triangles in clip
        // space; the vertex shader maps it to UV space.
        gl.bufferData(
            gl.ARRAY_BUFFER,
            new Float32Array([

                -1, -1,
                 1, -1,
                -1,  1,

                -1,  1,
                 1, -1,
                 1,  1
            ]),
            gl.STATIC_DRAW
        );

        STATE.videoUniforms = {

            position:
                gl.getAttribLocation(
                    STATE.videoProgram,
                    'a_position'
                ),

            video:
                gl.getUniformLocation(
                    STATE.videoProgram,
                    'u_video'
                ),

            sourceSize:
                gl.getUniformLocation(
                    STATE.videoProgram,
                    'u_sourceSize'
                ),

            sharpness:
                gl.getUniformLocation(
                    STATE.videoProgram,
                    'u_sharpness'
                ),

            recovery:
                gl.getUniformLocation(
                    STATE.videoProgram,
                    'u_recovery'
                )
        };

        return true;
    }


    // Walks up from the <video> element looking for the first
    // ancestor at least as large as the video itself — a decent
    // proxy for "the player chrome" without depending on YouTube's
    // (frequently changing) internal class names.
    function findPlayerContainer(
        video
    ) {

        let element =
            video.parentElement;

        while (
            element &&
            element !== document.body
        ) {

            const rect =
                element.getBoundingClientRect();

            if (
                rect.width >=
                    video.clientWidth &&
                rect.height >=
                    video.clientHeight
            ) {

                return element;
            }

            element =
                element.parentElement;
        }

        return video.parentElement;
    }


    function attachVideo(
        video
    ) {

        if (!video)
            return;

        if (
            STATE.video === video &&
            STATE.canvas
        ) {

            updateVideoVisibility();

            return;
        }

        STATE.video =
            video;

        if (
            !initializeVideo()
        )
            return;

        const container =
            findPlayerContainer(
                video
            );

        if (!container)
            return;

        const style =
            getComputedStyle(
                container
            );

        // The overlay canvas is absolutely positioned, so its
        // container needs a non-static position for `inset: 0` to
        // resolve against the player rather than the page.
        if (
            style.position ===
            'static'
        ) {

            container.style.position =
                'relative';
        }

        if (
            STATE.canvas.parentElement !==
            container
        ) {

            container.appendChild(
                STATE.canvas
            );
        }

        resizeVideo();

        updateVideoVisibility();

        log(
            'Video attached:',
            video.videoWidth,
            'x',
            video.videoHeight
        );
    }


    // Swaps visibility between the real <video> (made transparent,
    // but still driving playback/audio/captions) and our canvas
    // overlay drawn on top of it.
    function updateVideoVisibility() {

        if (!STATE.video)
            return;

        const active =
            CFG.master &&
            CFG.video.enabled;

        STATE.video.style.opacity =
            active
                ? '0'
                : '';

        STATE.video.style.pointerEvents =
            'none';

        if (STATE.canvas) {

            STATE.canvas.style.display =
                active
                    ? 'block'
                    : 'none';
        }
    }


    function resizeVideo() {

        if (
            !STATE.video ||
            !STATE.canvas ||
            !STATE.gl
        )
            return;

        const video =
            STATE.video;

        if (
            !video.videoWidth ||
            !video.videoHeight
        )
            return;

        const maximum =
            STATE.gl.getParameter(
                STATE.gl.MAX_VIEWPORT_DIMS
            );

        let width =
            Math.round(
                video.videoWidth *
                CFG.video.scale
            );

        let height =
            Math.round(
                video.videoHeight *
                CFG.video.scale
            );

        width =
            Math.min(
                width,
                maximum[0]
            );

        height =
            Math.min(
                height,
                maximum[1]
            );

        STATE.canvas.width =
            Math.max(
                1,
                width
            );

        STATE.canvas.height =
            Math.max(
                1,
                height
            );

        STATE.gl.viewport(
            0,
            0,
            STATE.canvas.width,
            STATE.canvas.height
        );

        STATE.lastVideoWidth =
            video.videoWidth;

        STATE.lastVideoHeight =
            video.videoHeight;
    }


    function renderVideo() {

        STATE.videoRAF =
            requestAnimationFrame(
                renderVideo
            );

        if (
            !STATE.video ||
            !STATE.canvas ||
            !STATE.gl
        )
            return;

        if (
            !CFG.master ||
            !CFG.video.enabled
        )
            return;

        const video =
            STATE.video;

        if (
            video.readyState <
            HTMLMediaElement.HAVE_CURRENT_DATA
        )
            return;

        if (
            video.videoWidth !==
                STATE.lastVideoWidth ||
            video.videoHeight !==
                STATE.lastVideoHeight
        ) {

            resizeVideo();
        }

        const gl =
            STATE.gl;

        gl.bindTexture(
            gl.TEXTURE_2D,
            STATE.videoTexture
        );

        try {

            gl.texImage2D(
                gl.TEXTURE_2D,
                0,
                gl.RGBA,
                gl.RGBA,
                gl.UNSIGNED_BYTE,
                video
            );

        } catch {

            // Can throw on a cross-origin/tainted frame or a video
            // that isn't ready yet; just skip this frame.
            return;
        }

        gl.useProgram(
            STATE.videoProgram
        );

        gl.bindBuffer(
            gl.ARRAY_BUFFER,
            STATE.videoBuffer
        );

        gl.enableVertexAttribArray(
            STATE.videoUniforms.position
        );

        gl.vertexAttribPointer(
            STATE.videoUniforms.position,
            2,
            gl.FLOAT,
            false,
            0,
            0
        );

        gl.activeTexture(
            gl.TEXTURE0
        );

        gl.bindTexture(
            gl.TEXTURE_2D,
            STATE.videoTexture
        );

        gl.uniform1i(
            STATE.videoUniforms.video,
            0
        );

        gl.uniform2f(
            STATE.videoUniforms.sourceSize,
            video.videoWidth,
            video.videoHeight
        );

        gl.uniform1f(
            STATE.videoUniforms.sharpness,
            CFG.video.sharpness
        );

        gl.uniform1f(
            STATE.videoUniforms.recovery,
            CFG.video.recovery
        );

        gl.drawArrays(
            gl.TRIANGLES,
            0,
            6
        );
    }


    /* ==========================================================
       GUI CSS
       ========================================================== */

    const GUI_CSS = `

#cosmic-otf {

    position: fixed;

    top: 80px;
    right: 24px;

    width: 360px;

    max-height:
        calc(100vh - 110px);

    overflow-y: auto;

    z-index:
        2147483647;

    color:
        #eeeeee;

    background:
        rgba(14,14,17,.96);

    border:
        1px solid
        rgba(255,255,255,.12);

    border-radius:
        14px;

    box-shadow:
        0 20px 70px
        rgba(0,0,0,.65);

    backdrop-filter:
        blur(18px);

    font:
        12px/1.4
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        sans-serif;

    user-select:
        none;
}

/* Hidden by default; toggled via the launcher pill, Alt+Shift+O,
   or opened automatically the first time the script boots if the
   user previously left it open. */
#cosmic-otf.cotf-hidden {

    display: none;
}

#cosmic-otf::-webkit-scrollbar {

    width: 7px;
}

#cosmic-otf::-webkit-scrollbar-thumb {

    background:
        #444;

    border-radius:
        10px;
}


/* Floating pill used to open/close the panel without needing to
   know the keyboard shortcut. Always on top, never blocks the
   player controls since it sits away from the seek bar. */
#cosmic-otf-launcher {

    position: fixed;

    top: 80px;
    right: 24px;

    z-index:
        2147483646;

    padding:
        8px 12px;

    color:
        #eee;

    background:
        rgba(20,20,24,.9);

    border:
        1px solid
        rgba(255,255,255,.15);

    border-radius:
        999px;

    font:
        650 11px/1
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        sans-serif;

    letter-spacing:
        .5px;

    cursor:
        pointer;

    box-shadow:
        0 6px 24px
        rgba(0,0,0,.5);

    user-select:
        none;
}

#cosmic-otf-launcher:hover {

    background:
        rgba(35,35,40,.95);
}

/* Hide the launcher while the panel itself is open, since the
   panel's own header can close it again. */
#cosmic-otf-launcher.cotf-hidden {

    display: none;
}


.cotf-header {

    padding:
        14px 16px;

    display:
        flex;

    justify-content:
        space-between;

    align-items:
        center;

    border-bottom:
        1px solid
        rgba(255,255,255,.08);
}


.cotf-header-controls {

    display:
        flex;

    align-items:
        center;

    gap:
        14px;
}


.cotf-header-toggle {

    display:
        flex;

    flex-direction:
        column;

    align-items:
        center;

    gap:
        4px;
}


.cotf-header-toggle-label {

    color:
        #777;

    font-size:
        9px;

    letter-spacing:
        .5px;

    white-space:
        nowrap;
}


.cotf-close {

    color:
        #999;

    font-size:
        16px;

    line-height:
        1;

    cursor:
        pointer;

    padding:
        2px 4px;
}


.cotf-close:hover {

    color:
        #fff;
}


.cotf-title {

    font-size:
        15px;

    font-weight:
        700;

    letter-spacing:
        .5px;
}


.cotf-subtitle {

    color:
        #777;

    font-size:
        10px;
}


.cotf-section {

    border-bottom:
        1px solid
        rgba(255,255,255,.07);
}


.cotf-section-header {

    padding:
        11px 14px;

    display:
        flex;

    justify-content:
        space-between;

    align-items:
        center;

    cursor:
        pointer;
}


.cotf-section-header:hover {

    background:
        rgba(255,255,255,.04);
}


.cotf-section-title {

    font-weight:
        650;
}


.cotf-content {

    padding:
        0 14px 14px;
}


.cotf-row {

    display:
        grid;

    grid-template-columns:
        92px 1fr 55px;

    gap:
        8px;

    align-items:
        center;

    margin:
        8px 0;
}


.cotf-label {

    color:
        #aaa;
}


.cotf-value {

    text-align:
        right;

    color:
        #fff;

    font-variant-numeric:
        tabular-nums;
}


.cotf-group {

    margin-top:
        12px;

    margin-bottom:
        6px;

    color:
        #777;

    font-size:
        10px;

    letter-spacing:
        .8px;
}


#cosmic-otf input[type="range"] {

    width:
        100%;

    accent-color:
        #ddd;

    cursor:
        pointer;
}


#cosmic-otf select {

    width:
        100%;

    padding:
        5px;

    background:
        #222;

    color:
        #eee;

    border:
        1px solid #444;

    border-radius:
        6px;
}


#cosmic-otf button {

    padding:
        6px 9px;

    color:
        #eee;

    background:
        #252525;

    border:
        1px solid #444;

    border-radius:
        7px;

    cursor:
        pointer;
}


#cosmic-otf button:hover {

    background:
        #333;
}


.cotf-switch {

    width:
        34px;

    height:
        18px;

    border-radius:
        20px;

    background:
        #444;

    position:
        relative;

    cursor:
        pointer;
}


.cotf-switch::after {

    content:
        '';

    width:
        14px;

    height:
        14px;

    border-radius:
        50%;

    background:
        #888;

    position:
        absolute;

    top:
        2px;

    left:
        2px;

    transition:
        .15s;
}


.cotf-switch.on {

    background:
        #666;
}


.cotf-switch.on::after {

    left:
        18px;

    background:
        #fff;
}


/* Smaller variant used inline in the header, e.g. the "More
   options" toggle, so it doesn't compete visually with the master
   bypass switch. */
.cotf-switch.cotf-switch-small {

    width:
        28px;

    height:
        16px;
}

.cotf-switch.cotf-switch-small::after {

    width:
        12px;

    height:
        12px;
}

.cotf-switch.cotf-switch-small.on::after {

    left:
        14px;
}


.cotf-status {

    padding:
        10px 14px;

    color:
        #777;

    font-size:
        10px;
}


.cotf-good {

    color:
        #91d391;
}


.cotf-bad {

    color:
        #e58d8d;
}


.cotf-buttons {

    display:
        grid;

    grid-template-columns:
        1fr 1fr;

    gap:
        6px;
}


.cotf-reset {

    width:
        100%;

    margin-top:
        6px;
}

`;


    function injectGUIStyle() {

        if (
            document.getElementById(
                'cosmic-otf-style'
            )
        )
            return;

        const style =
            document.createElement(
                'style'
            );

        style.id =
            'cosmic-otf-style';

        style.textContent =
            GUI_CSS;

        document.head.appendChild(
            style
        );
    }


    /* ==========================================================
       GUI BUILD
       ========================================================== */

    function formatValue(
        key,
        value
    ) {

        if (
            key ===
            'video.scale'
        ) {

            return (
                Number(value)
                    .toFixed(2) +
                '×'
            );
        }

        if (
            key.includes(
                'sharpness'
            ) ||
            key.includes(
                'recovery'
            ) ||
            key.includes(
                'clarity'
            ) ||
            key.includes(
                'compression'
            )
        ) {

            return (
                Math.round(
                    Number(value) * 100
                ) +
                '%'
            );
        }

        if (
            key ===
            'audio.stereo'
        ) {

            return (
                Number(value)
                    .toFixed(2)
            );
        }

        return (
            Number(value)
                .toFixed(1) +
            (
                key.includes(
                    'audio'
                )
                    ? ' dB'
                    : ''
            )
        );
    }


    function slider(
        label,
        key,
        minimum,
        maximum,
        step
    ) {

        const value =
            getPath(key);

        return `

            <div class="cotf-row">

                <span class="cotf-label">
                    ${label}
                </span>

                <input
                    type="range"
                    min="${minimum}"
                    max="${maximum}"
                    step="${step}"
                    value="${value}"
                    data-key="${key}"
                >

                <span
                    class="cotf-value"
                    data-value="${key}"
                >
                    ${formatValue(
                        key,
                        value
                    )}
                </span>

            </div>
        `;
    }


    function buildGUI() {

        if (STATE.panel)
            return;

        injectGUIStyle();

        const panel =
            document.createElement(
                'div'
            );

        panel.id =
            'cosmic-otf';

        panel.innerHTML = `

            <div class="cotf-header">

                <div>

                    <div class="cotf-title">
                        COSMIC OTF
                    </div>

                    <div class="cotf-subtitle">
                        YouTube realtime processing
                    </div>

                </div>

                <div class="cotf-header-controls">

                    <!-- "More options" reveals the Advanced Audio
                         section below without leaving the main
                         screen; state is persisted like everything
                         else. -->
                    <div class="cotf-header-toggle">

                        <span class="cotf-header-toggle-label">
                            More options
                        </span>

                        <div
                            class="cotf-switch cotf-switch-small"
                            data-advanced-switch
                            title="Show advanced audio controls"
                        ></div>

                    </div>

                    <div
                        class="cotf-switch on"
                        data-master
                        title="Master bypass"
                    ></div>

                    <span
                        class="cotf-close"
                        data-close-panel
                        title="Close panel (Alt+Shift+O)"
                    >
                        ✕
                    </span>

                </div>

            </div>


            <!-- VIDEO -->

            <div class="cotf-section">

                <div
                    class="cotf-section-header"
                    data-collapse="video"
                >

                    <span class="cotf-section-title">
                        VIDEO
                    </span>

                    <span>
                        ▼
                    </span>

                </div>


                <div
                    class="cotf-content"
                    data-section="video"
                >

                    <div class="cotf-row">

                        <span class="cotf-label">
                            Enabled
                        </span>

                        <span></span>

                        <div
                            class="cotf-switch on"
                            data-video-switch
                        ></div>

                    </div>


                    ${slider(
                        'Scale',
                        'video.scale',
                        1,
                        4,
                        0.25
                    )}


                    ${slider(
                        'Sharpness',
                        'video.sharpness',
                        0,
                        0.5,
                        0.01
                    )}


                    ${slider(
                        'Recovery',
                        'video.recovery',
                        0,
                        0.5,
                        0.01
                    )}

                </div>

            </div>


            <!-- AUDIO -->

            <div class="cotf-section">

                <div
                    class="cotf-section-header"
                    data-collapse="audio"
                >

                    <span class="cotf-section-title">
                        AUDIO
                    </span>

                    <span>
                        ▼
                    </span>

                </div>


                <div
                    class="cotf-content"
                    data-section="audio"
                >

                    <div class="cotf-row">

                        <span class="cotf-label">
                            Enabled
                        </span>

                        <span></span>

                        <div
                            class="cotf-switch on"
                            data-audio-switch
                        ></div>

                    </div>


                    ${slider(
                        'Preamp',
                        'audio.preamp',
                        -12,
                        6,
                        0.1
                    )}


                    <div class="cotf-group">
                        PARAMETRIC EQ
                    </div>


                    ${slider(
                        '32 Hz',
                        'audio.eq.b32',
                        -6,
                        6,
                        0.1
                    )}

                    ${slider(
                        '80 Hz',
                        'audio.eq.b80',
                        -6,
                        6,
                        0.1
                    )}

                    ${slider(
                        '160 Hz',
                        'audio.eq.b160',
                        -6,
                        6,
                        0.1
                    )}

                    ${slider(
                        '320 Hz',
                        'audio.eq.b320',
                        -6,
                        6,
                        0.1
                    )}

                    ${slider(
                        '640 Hz',
                        'audio.eq.b640',
                        -6,
                        6,
                        0.1
                    )}

                    ${slider(
                        '1.2 kHz',
                        'audio.eq.b1200',
                        -6,
                        6,
                        0.1
                    )}

                    ${slider(
                        '2.4 kHz',
                        'audio.eq.b2400',
                        -6,
                        6,
                        0.1
                    )}

                    ${slider(
                        '4.8 kHz',
                        'audio.eq.b4800',
                        -6,
                        6,
                        0.1
                    )}

                    ${slider(
                        '9.6 kHz',
                        'audio.eq.b9600',
                        -6,
                        6,
                        0.1
                    )}

                    ${slider(
                        '16 kHz',
                        'audio.eq.b16000',
                        -6,
                        6,
                        0.1
                    )}


                    <div class="cotf-group">
                        RECOVERY
                    </div>


                    ${slider(
                        'Air',
                        'audio.air',
                        -3,
                        3,
                        0.1
                    )}


                    ${slider(
                        'Clarity',
                        'audio.clarity',
                        0,
                        1,
                        0.01
                    )}

                </div>

            </div>


            <!-- ADVANCED (More options) -->

            <div class="cotf-section">

                <div
                    class="cotf-section-header"
                    data-collapse="advanced"
                >

                    <span class="cotf-section-title">
                        ADVANCED AUDIO
                    </span>

                    <span>
                        ▼
                    </span>

                </div>


                <div
                    class="cotf-content"
                    data-section="advanced"
                >

                    ${slider(
                        'Compression',
                        'audio.compression',
                        0,
                        1,
                        0.01
                    )}


                    ${slider(
                        'Ceiling',
                        'audio.limiter',
                        -12,
                        -0.1,
                        0.1
                    )}


                    ${slider(
                        'Stereo',
                        'audio.stereo',
                        -1,
                        1,
                        0.01
                    )}

                </div>

            </div>


            <!-- PRESETS -->

            <div class="cotf-section">

                <div class="cotf-section-header">

                    <span class="cotf-section-title">
                        PRESET
                    </span>

                </div>


                <div class="cotf-content">

                    <select data-preset>

                        ${Object.keys(
                            PRESETS
                        ).map(
                            name =>
                                `
                                <option
                                    value="${name}"
                                    ${
                                        CFG.preset === name
                                            ? 'selected'
                                            : ''
                                    }
                                >
                                    ${name}
                                </option>
                                `
                        ).join('')}

                    </select>


                    <div
                        class="cotf-buttons"
                        style="margin-top:7px"
                    >

                        <button
                            data-save
                        >
                            Save
                        </button>

                        <button
                            data-reset
                        >
                            Reset
                        </button>

                    </div>

                </div>

            </div>


            <!-- STATUS -->

            <div class="cotf-status">

                <div>
                    GPU:
                    <span data-gpu>
                        waiting
                    </span>
                </div>

                <div>
                    Audio:
                    <span data-audio>
                        waiting
                    </span>
                </div>

                <div>
                    Source:
                    <span data-source>
                        waiting
                    </span>
                </div>

                <div style="margin-top:6px;color:#555">
                    Alt+Shift+O toggles this panel ·
                    Alt+Shift+U toggles processing
                </div>

            </div>

        `;

        document.body.appendChild(
            panel
        );

        STATE.panel =
            panel;

        bindGUI();

        refreshGUI();
    }


    /* ==========================================================
       LAUNCHER (floating open/close pill)
       ========================================================== */

    function buildLauncher() {

        if (STATE.launcher)
            return;

        injectGUIStyle();

        const launcher =
            document.createElement(
                'div'
            );

        launcher.id =
            'cosmic-otf-launcher';

        launcher.textContent =
            'OTF';

        launcher.title =
            'Open Cosmic OTF settings (Alt+Shift+O)';

        launcher.addEventListener(
            'click',
            () => {

                setPanelOpen(true);
            }
        );

        document.body.appendChild(
            launcher
        );

        STATE.launcher =
            launcher;
    }


    /* ==========================================================
       PANEL OPEN/CLOSE + MORE OPTIONS
       ========================================================== */

    // Single source of truth for whether the panel is visible.
    // Keeps CFG.ui.open, the DOM, and localStorage all in sync so
    // callers (keyboard, launcher click, header ✕) don't repeat
    // this bookkeeping.
    function setPanelOpen(open) {

        CFG.ui.open =
            !!open;

        if (STATE.panel) {

            STATE.panel.classList.toggle(
                'cotf-hidden',
                !CFG.ui.open
            );
        }

        if (STATE.launcher) {

            // Hide the launcher while the panel itself is on
            // screen; its own ✕ can close it again.
            STATE.launcher.classList.toggle(
                'cotf-hidden',
                CFG.ui.open
            );
        }

        saveConfig();
    }


    function togglePanelOpen() {

        setPanelOpen(
            !CFG.ui.open
        );
    }


    // Shows/hides the Advanced Audio section from the header
    // switch, independent of that section's own collapse arrow.
    function setAdvancedVisible(visible) {

        CFG.ui.advanced =
            !!visible;

        if (STATE.panel) {

            const section =
                STATE.panel.querySelector(
                    '[data-section="advanced"]'
                );

            if (section) {

                section.style.display =
                    CFG.ui.advanced
                        ? ''
                        : 'none';
            }

            const toggle =
                STATE.panel.querySelector(
                    '[data-advanced-switch]'
                );

            if (toggle) {

                toggle.classList.toggle(
                    'on',
                    CFG.ui.advanced
                );
            }
        }

        saveConfig();
    }


    /* ==========================================================
       GUI EVENTS
       ========================================================== */

    function bindGUI() {

        const panel =
            STATE.panel;


        panel.querySelector(
            '[data-master]'
        ).addEventListener(
            'click',
            () => {

                CFG.master =
                    !CFG.master;

                updateMaster();

                sendAudioConfig();

                saveConfig();
            }
        );


        // Header "More options" switch — purely a visibility
        // toggle, it never touches audio/video values themselves.
        panel.querySelector(
            '[data-advanced-switch]'
        ).addEventListener(
            'click',
            () => {

                setAdvancedVisible(
                    !CFG.ui.advanced
                );
            }
        );


        panel.querySelector(
            '[data-close-panel]'
        ).addEventListener(
            'click',
            () => {

                setPanelOpen(false);
            }
        );


        panel.querySelector(
            '[data-video-switch]'
        ).addEventListener(
            'click',
            () => {

                CFG.video.enabled =
                    !CFG.video.enabled;

                updateVideoVisibility();

                refreshGUI();

                saveConfig();
            }
        );


        panel.querySelector(
            '[data-audio-switch]'
        ).addEventListener(
            'click',
            () => {

                CFG.audio.enabled =
                    !CFG.audio.enabled;

                sendAudioConfig();

                refreshGUI();

                saveConfig();
            }
        );


        panel.querySelectorAll(
            'input[data-key]'
        ).forEach(
            input => {

                input.addEventListener(
                    'input',
                    () => {

                        const key =
                            input.dataset.key;

                        const value =
                            parseFloat(
                                input.value
                            );

                        setPath(
                            key,
                            value
                        );

                        const output =
                            panel.querySelector(
                                `[data-value="${key}"]`
                            );

                        if (output) {

                            output.textContent =
                                formatValue(
                                    key,
                                    value
                                );
                        }


                        if (
                            key.startsWith(
                                'video.'
                            )
                        ) {

                            resizeVideo();

                        } else {

                            sendAudioConfig();
                        }

                        saveConfig();
                    }
                );
            }
        );


        panel.querySelector(
            '[data-preset]'
        ).addEventListener(
            'change',
            event => {

                applyPreset(
                    event.target.value
                );
            }
        );


        panel.querySelector(
            '[data-save]'
        ).addEventListener(
            'click',
            () => {

                saveConfig();

                const button =
                    panel.querySelector(
                        '[data-save]'
                    );

                const previous =
                    button.textContent;

                button.textContent =
                    'Saved';

                setTimeout(
                    () => {

                        button.textContent =
                            previous;

                    },
                    800
                );
            }
        );


        panel.querySelector(
            '[data-reset]'
        ).addEventListener(
            'click',
            () => {

                // Resetting restores factory defaults but keeps the
                // panel's own open/advanced state as the user has
                // it — resetting sliders shouldn't also close the
                // panel out from under them.
                const ui =
                    CFG.ui;

                CFG =
                    structuredClone(
                        DEFAULTS
                    );

                CFG.ui =
                    ui;

                saveConfig();

                sendAudioConfig();

                resizeVideo();

                refreshGUI();
            }
        );


        panel.querySelectorAll(
            '[data-collapse]'
        ).forEach(
            header => {

                header.addEventListener(
                    'click',
                    () => {

                        const section =
                            panel.querySelector(
                                `[data-section="${header.dataset.collapse}"]`
                            );

                        if (!section)
                            return;

                        const hidden =
                            section.style.display ===
                            'none';

                        section.style.display =
                            hidden
                                ? ''
                                : 'none';

                        // Keep the header switch in sync if this is
                        // the Advanced section, since it can now be
                        // toggled from two places.
                        if (
                            header.dataset.collapse ===
                            'advanced'
                        ) {

                            CFG.ui.advanced =
                                hidden;

                            saveConfig();

                            const toggle =
                                panel.querySelector(
                                    '[data-advanced-switch]'
                                );

                            if (toggle) {

                                toggle.classList.toggle(
                                    'on',
                                    hidden
                                );
                            }
                        }
                    }
                );
            }
        );
    }


    function updateMaster() {

        const switchElement =
            STATE.panel?.querySelector(
                '[data-master]'
            );

        if (switchElement) {

            switchElement.classList.toggle(
                'on',
                CFG.master
            );
        }

        updateVideoVisibility();
    }


    function refreshGUI() {

        if (!STATE.panel)
            return;

        STATE.panel
            .querySelectorAll(
                'input[data-key]'
            )
            .forEach(
                input => {

                    const value =
                        getPath(
                            input.dataset.key
                        );

                    input.value =
                        value;

                    const output =
                        STATE.panel.querySelector(
                            `[data-value="${input.dataset.key}"]`
                        );

                    if (output) {

                        output.textContent =
                            formatValue(
                                input.dataset.key,
                                value
                            );
                    }
                }
            );


        const master =
            STATE.panel.querySelector(
                '[data-master]'
            );

        master.classList.toggle(
            'on',
            CFG.master
        );


        const videoSwitch =
            STATE.panel.querySelector(
                '[data-video-switch]'
            );

        videoSwitch.classList.toggle(
            'on',
            CFG.video.enabled
        );


        const audioSwitch =
            STATE.panel.querySelector(
                '[data-audio-switch]'
            );

        audioSwitch.classList.toggle(
            'on',
            CFG.audio.enabled
        );


        const preset =
            STATE.panel.querySelector(
                '[data-preset]'
            );

        if (preset) {

            preset.value =
                CFG.preset;
        }


        // Re-apply the persisted panel/advanced visibility so a
        // full refresh (e.g. after Reset) doesn't silently reopen
        // sections the user had hidden.
        setPanelOpen(
            CFG.ui.open
        );

        setAdvancedVisible(
            CFG.ui.advanced
        );


        updateStatus();
    }


    /* ==========================================================
       STATUS
       ========================================================== */

    function updateStatus() {

        if (!STATE.panel)
            return;


        const gpu =
            STATE.panel.querySelector(
                '[data-gpu]'
            );

        if (gpu) {

            gpu.textContent =
                STATE.gl
                    ? 'WebGL2'
                    : 'waiting';

            gpu.className =
                STATE.gl
                    ? 'cotf-good'
                    : '';
        }


        const audio =
            STATE.panel.querySelector(
                '[data-audio]'
            );

        if (audio) {

            if (
                STATE.audioContext
            ) {

                audio.textContent =
                    `${Math.round(
                        STATE.audioContext.sampleRate
                    )} Hz`;

                audio.className =
                    'cotf-good';

            } else if (
                STATE.audioFailed
            ) {

                audio.textContent =
                    'failed';

                audio.className =
                    'cotf-bad';

            } else {

                audio.textContent =
                    'waiting';

                audio.className =
                    '';
            }
        }


        const source =
            STATE.panel.querySelector(
                '[data-source]'
            );

        if (source) {

            if (
                STATE.video &&
                STATE.video.videoWidth
            ) {

                source.textContent =
                    `${STATE.video.videoWidth}×${STATE.video.videoHeight}`;

            } else {

                source.textContent =
                    'waiting';
            }
        }
    }


    /* ==========================================================
       PLAYER MONITOR
       ========================================================== */

    // Polls for the <video> element rather than relying purely on
    // MutationObserver, because YouTube's SPA navigation swaps the
    // player element out in ways that are easy to miss with a
    // narrowly-scoped observer.
    async function monitorPlayer() {

        const video =
            document.querySelector(
                'video'
            );

        if (!video)
            return;


        /*
         * Detect YouTube player replacement.
         */
        if (
            video !== STATE.video
        ) {

            log(
                'New YouTube video element'
            );

            /*
             * The old AudioContext is no longer useful
             * for the new media element.
             */
            if (
                STATE.audioContext &&
                STATE.audioVideo !== video
            ) {

                try {

                    await STATE.audioContext
                        .close();

                } catch {}

                STATE.audioContext =
                    null;

                STATE.audioSource =
                    null;

                STATE.audioWorklet =
                    null;

                STATE.audioVideo =
                    null;
            }

            attachVideo(
                video
            );

            await initializeAudio(
                video
            );
        }


        /*
         * Resume after user interaction/autoplay.
         */
        if (
            STATE.audioContext &&
            STATE.audioContext.state ===
                'suspended' &&
            !video.paused
        ) {

            try {

                await STATE.audioContext
                    .resume();

            } catch {}
        }


        updateStatus();
    }


    /* ==========================================================
       USER-ACTIVATION AUDIO RESUME
       ========================================================== */

    // Browsers require a user gesture before an AudioContext will
    // actually start producing sound; this listens for the first
    // gesture of nearly any kind and nudges a suspended context
    // awake without requiring the user to interact with our panel
    // specifically.
    function installAudioResume() {

        const resume =
            async () => {

                if (
                    STATE.audioContext &&
                    STATE.audioContext.state ===
                        'suspended'
                ) {

                    try {

                        await STATE.audioContext
                            .resume();

                    } catch {}
                }
            };


        [
            'click',
            'pointerdown',
            'keydown',
            'touchstart'
        ].forEach(
            event => {

                document.addEventListener(
                    event,
                    resume,
                    {
                        passive: true,
                        capture: true
                    }
                );
            }
        );
    }


    /* ==========================================================
       KEYBOARD SHORTCUTS
       ========================================================== */

    function installKeyboard() {

        document.addEventListener(
            'keydown',
            event => {

                // Alt+Shift+O — open/close the settings panel.
                // This is the primary "invoke the UI" shortcut; it
                // does not touch processing itself.
                if (
                    event.altKey &&
                    event.shiftKey &&
                    event.code === 'KeyO'
                ) {

                    event.preventDefault();

                    togglePanelOpen();

                    return;
                }

                // Alt+Shift+U — master bypass. Lets you A/B the
                // effect instantly without opening the panel at
                // all.
                if (
                    event.altKey &&
                    event.shiftKey &&
                    event.code === 'KeyU'
                ) {

                    event.preventDefault();

                    CFG.master =
                        !CFG.master;

                    updateMaster();

                    sendAudioConfig();

                    saveConfig();

                    refreshGUI();
                }
            },
            true
        );
    }


    /* ==========================================================
       BOOT
       ========================================================== */

    function boot() {

        if (
            STATE.initialized
        )
            return;

        STATE.initialized =
            true;

        buildGUI();

        buildLauncher();

        // Restore whatever open/advanced state was last saved,
        // rather than always starting closed.
        setPanelOpen(
            CFG.ui.open
        );

        setAdvancedVisible(
            CFG.ui.advanced
        );

        installKeyboard();

        installAudioResume();

        setInterval(
            monitorPlayer,
            750
        );

        STATE.videoRAF =
            requestAnimationFrame(
                renderVideo
            );

        monitorPlayer();

        log(
            `Cosmic OTF v${VERSION} loaded — Alt+Shift+O opens the panel, Alt+Shift+U toggles processing`
        );
    }


    if (
        document.readyState ===
        'loading'
    ) {

        document.addEventListener(
            'DOMContentLoaded',
            boot,
            {
                once: true
            }
        );

    } else {

        boot();
    }

})();
