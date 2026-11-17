// WebGL renderer for the Life field: every cell is a small polished tile. Raw WebGL 1, no
// dependencies. The CPU decides which cells are on (simulation + Bayer thinning); the shader
// decides how they look:
//   - per cell: a hard-stepped bevel (light top-left edge, dark bottom-right edge, corner glint)
//   - across cells: a surface normal from neighbour occupancy, lit by one shared light, plus a
//     narrow specular band that drifts across the pane, so a mass reads as one lacquered surface
//   - iridescence: hue slides emerald -> aqua -> blue with position relative to the light
//   - tones are quantised (dark, body, bright, hot) so cells stay crisp pixels, never gradients

const VERT = `
attribute vec2 p;
void main() { gl_Position = vec4(p, 0.0, 1.0); }
`;

const FRAG = `
precision mediump float;
uniform sampler2D uCells;
uniform vec2 uGrid;      // cols, rows
uniform vec2 uCanvas;    // device px
uniform float uCell;     // device px per cell
uniform float uTime;     // seconds
uniform float uIntensity;

const vec3 BG = vec3(0.039, 0.047, 0.043);
const vec3 EMERALD = vec3(0.463, 0.784, 0.647);
const vec3 AQUA = vec3(0.345, 0.702, 0.702);
const vec3 BLUE = vec3(0.290, 0.525, 0.784);
const vec3 SHEEN = vec3(0.86, 1.0, 0.95);   // white-green, never warm

vec4 cellAt(vec2 c) {
  if (c.x < 0.0 || c.y < 0.0 || c.x >= uGrid.x || c.y >= uGrid.y) return vec4(0.0);
  return texture2D(uCells, (c + 0.5) / uGrid);
}
float occ(vec2 c) {
  float r = cellAt(c).r;
  return r > 0.9 ? 1.0 : r > 0.5 ? 0.55 : r > 0.2 ? 0.3 : 0.0;
}
vec3 family(float g, float shift) {
  // g: 0 green, 0.5 aqua, 1 blue; shift slides one step toward blue (iridescence)
  float h = clamp(g * 2.0 + shift, 0.0, 2.0);
  return h < 1.0 ? mix(EMERALD, AQUA, h) : mix(AQUA, BLUE, h - 1.0);
}

void main() {
  vec2 px = vec2(gl_FragCoord.x, uCanvas.y - gl_FragCoord.y);
  vec2 c = floor(px / uCell);
  vec2 f = px - c * uCell;
  vec4 t = cellAt(c);
  if (t.r < 0.1) { gl_FragColor = vec4(BG, 1.0); return; }
  float level = t.r > 0.9 ? 1.0 : t.r > 0.5 ? 0.62 : 0.4;
  bool live = t.r > 0.9;

  // height field from neighbours -> normal (x right, y down, z out of the screen)
  float l = occ(c + vec2(-1.0, 0.0)), r = occ(c + vec2(1.0, 0.0));
  float u = occ(c + vec2(0.0, -1.0)), d = occ(c + vec2(0.0, 1.0));
  float ul = occ(c + vec2(-1.0, -1.0)), ur = occ(c + vec2(1.0, -1.0));
  float dl = occ(c + vec2(-1.0, 1.0)), dr = occ(c + vec2(1.0, 1.0));
  float gx = (r + 0.5 * (ur + dr)) - (l + 0.5 * (ul + dl));
  float gy = (d + 0.5 * (dl + dr)) - (u + 0.5 * (ul + ur));
  float crowd = (l + r + u + d + ul + ur + dl + dr) / 8.0;
  vec3 n = normalize(vec3(-gx * 0.55, -gy * 0.55, 1.0));

  // one shared light, slowly swinging; a narrow specular band sweeps the pane diagonally
  float a = 2.35 + 0.35 * sin(uTime * 0.11);
  vec3 L = normalize(vec3(cos(a), sin(a), 0.9));
  vec2 q = (c + 0.5) / uGrid;
  float along = dot(q, normalize(vec2(1.0, 0.75)));
  float centre = fract(uTime / 16.0) * 1.6 - 0.3;
  float band = exp(-pow((along - centre + n.x * 0.1 + n.y * 0.08) / 0.12, 2.0));
  float diffuse = max(dot(n, L), 0.0);
  vec3 H = normalize(L + vec3(0.0, 0.0, 1.0));
  float spec = pow(max(dot(n, H), 0.0), 24.0);

  // score -> four hard tones. Interior of masses sits darker and richer; light-facing rims and
  // the band go hot. Isolated cells (crowd 0) keep a modest body tone.
  float score = 0.24 + 0.38 * diffuse + 0.7 * band * (0.5 + 0.5 * spec) + 0.3 * spec - 0.2 * crowd * (1.0 - band);

  // per-cell bevel: 1 device px (more on big cells) light edge top-left, dark edge bottom-right,
  // and a hot corner glint where the cell is already lit
  float e = max(1.0, floor(uCell * 0.17));
  bool lit = score > 0.5;
  // rims only where the mass ends, so joined cells read as one plate with an outer bevel
  bool openL = l < 0.5, openU = u < 0.5, openR = r < 0.5, openD = d < 0.5;
  if ((f.x < e && openL) || (f.y < e && openU)) score += 0.26;
  if ((f.x >= uCell - e && openR) || (f.y >= uCell - e && openD)) score = min(score - 0.36, 0.3);
  // inside a plate, a faint seam keeps the pixel grid legible without breaking the surface
  if (f.x >= uCell - e && !openR) score -= 0.08;
  if (f.y >= uCell - e && !openD) score -= 0.08;
  if (f.x < e * 2.0 && f.y < e * 2.0 && lit && (openL || openU)) score += 0.4;

  if (!live) score = min(score, 0.7);

  float shift = 0.55 * (0.5 + 0.5 * sin((along - centre) * 9.0 + n.x * 2.0));
  vec3 base = family(t.g / 0.996, shift);
  // intensity tames the body tones; highlights keep their heat so the contrast survives
  vec3 col;
  float k = uIntensity;
  if (score < 0.36) col = BG + (base * 0.24 - BG) * k;                 // deep, saturated dark
  else if (score < 0.62) col = BG + (base * 0.72 - BG) * k;            // body
  else if (score < 0.9) col = mix(base * 1.08, SHEEN, 0.22);           // bright
  else col = mix(base, SHEEN, 0.72);                                   // hot glint
  col = BG + (col - BG) * level;
  gl_FragColor = vec4(col, 1.0);
}
`;

export interface Metal {
  resize(cols: number, rows: number, cellDev: number): void;
  upload(cells: Uint8Array): void;
  draw(time: number): void;
  readonly gl: WebGLRenderingContext;
}

export function createMetal(canvas: HTMLCanvasElement, intensity: number): Metal | null {
  const gl = canvas.getContext('webgl', { antialias: false, alpha: false, premultipliedAlpha: false, preserveDrawingBuffer: true });
  if (!gl) return null;
  const sh = (type: number, src: string) => {
    const s = gl.createShader(type)!;
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || 'shader');
    return s;
  };
  let prog: WebGLProgram;
  try {
    prog = gl.createProgram()!;
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT));
    gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return null;
  } catch {
    return null;
  }
  gl.useProgram(prog);
  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, 'p');
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  const U = (n: string) => gl.getUniformLocation(prog, n);
  const uGrid = U('uGrid'), uCanvas = U('uCanvas'), uCell = U('uCell'), uTime = U('uTime'), uInt = U('uIntensity');
  gl.uniform1i(U('uCells'), 0);
  gl.uniform1f(uInt, intensity);
  let cols = 1, rows = 1;
  return {
    gl,
    resize(c, r, cellDev) {
      cols = c;
      rows = r;
      canvas.width = c * cellDev;
      canvas.height = r * cellDev;
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(uGrid, c, r);
      gl.uniform2f(uCanvas, canvas.width, canvas.height);
      gl.uniform1f(uCell, cellDev);
    },
    upload(cells) {
      gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, cols, rows, 0, gl.RGBA, gl.UNSIGNED_BYTE, cells);
    },
    draw(time) {
      gl.uniform1f(uTime, time);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    },
  };
}
