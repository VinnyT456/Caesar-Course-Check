<script>
  import { onMount, onDestroy } from 'svelte'
  import { api } from './api.js'

  let s = $state(null)
  let form = $state({ term: '', subject: '', catalog_nbr: '', seat_limit: 150, interval: 60 })
  let formLoaded = false
  const OTHER = '__other'
  let catalog = $state({ term: null, schools: [] })
  let manual = $state({ term: false, subject: false, course: false })
  let err = $state('')
  let tab = $state('course')
  let lastAlert = 0
  let timer
  let ticker = $state(Date.now())
  let pollAt = $state(Date.now())
  let audio
  // Inside the macOS menu bar popover the app is the whole UI: fixed height, plus a Quit button.
  const isPopover = new URLSearchParams(location.search).get('view') === 'popover'

  const HEAD = {
    idle: 'Ready', signing_in: 'Waiting for captcha', starting: 'Starting', monitoring: 'Monitoring',
    needs_signin: 'Captcha needed', alert: 'Seat available', error: 'Something went wrong',
  }
  const TONE = {
    idle: 'neutral', signing_in: 'warn', starting: 'warn', monitoring: 'ok',
    needs_signin: 'bad', alert: 'ok', error: 'bad',
  }
  const TABS = [['course', 'Course'], ['log', 'Activity']]

  async function poll() {
    try {
      s = await api('/api/state')
      pollAt = Date.now()
      err = ''
      if (!formLoaded) { form = { ...s.config }; formLoaded = true }
      else if (s.busy && s.capacity != null) form.seat_limit = s.config.seat_limit  // auto-set from the class page
      if (s.alert_id > lastAlert) { if (lastAlert !== 0 || s.status === 'alert') beep(); lastAlert = s.alert_id }
    } catch { err = 'Lost connection to the app backend.' }
  }

  function unlockAudio() {
    // WebKit only allows audio after a user gesture: create/resume the context on click.
    try { audio ??= new AudioContext(); audio.resume() } catch {}
  }
  function beep() {
    try {
      unlockAudio()
      const ctx = audio
      ;[0, 0.25, 0.5].forEach((t) => {
        const o = ctx.createOscillator(), g = ctx.createGain()
        o.frequency.value = 880; o.connect(g); g.connect(ctx.destination)
        g.gain.setValueAtTime(0.2, ctx.currentTime + t)
        g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + t + 0.2)
        o.start(ctx.currentTime + t); o.stop(ctx.currentTime + t + 0.22)
      })
    } catch {}
  }

  async function signIn(e) { try { await api('/api/signin', { trusted: e?.isTrusted, detail: e?.detail, type: e?.type, pointer: e?.pointerType, x: e?.clientX, y: e?.clientY, vis: document.visibilityState, focus: document.hasFocus() }); poll() } catch (e) { err = e.message } }
  async function start() {
    unlockAudio()
    try {
      await api('/api/start', { ...form, seat_limit: +form.seat_limit, interval: +form.interval })
      poll()
    } catch (e) { err = 'Check the course fields: ' + e.message }
  }
  async function quit() { try { await api('/api/app/quit', {}) } catch {} }
  async function testAlert() { try { await api('/api/app/test-alert', {}) } catch (e) { err = e.message } }
  async function openCaesar() { try { await api('/api/app/caesar', {}) } catch (e) { err = e.message } }
  async function stop() { try { await api('/api/stop', {}); poll() } catch (e) { err = e.message } }

  function onTabKey(e) {
    const i = TABS.findIndex(([k]) => k === tab)
    const n = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : null
    if (n === null) return
    tab = TABS[(n + TABS.length) % TABS.length][0]
    document.getElementById('tab-' + tab)?.focus()
  }

  async function loadCatalog() {
    try { catalog = await api('/api/catalog') } catch { /* dropdowns fall back to typing */ }
  }
  onMount(() => { loadCatalog(); poll(); timer = setInterval(() => { poll(); ticker = Date.now() }, 1500) })
  onDestroy(() => clearInterval(timer))

  // One entry per subject code (a code can be listed under several schools); courses merged.
  let subjectGroups = $derived.by(() => {
    const seen = new Map()
    const groups = []
    for (const sc of catalog.schools) {
      const items = []
      for (const sub of sc.subjects) {
        const have = seen.get(sub.code)
        if (have) {
          const known = new Set(have.courses.map((c) => c.nbr))
          for (const c of sub.courses) if (!known.has(c.nbr)) have.courses.push(c)
        } else {
          const entry = { ...sub, courses: [...sub.courses] }
          seen.set(sub.code, entry)
          items.push(entry)
        }
      }
      if (items.length) groups.push({ school: sc.name, items })
    }
    for (const e of seen.values()) e.courses.sort((a, b) => a.nbr.localeCompare(b.nbr, undefined, { numeric: true }))
    return { groups, byCode: seen }
  })
  let courseList = $derived(subjectGroups.byCode.get(form.subject)?.courses ?? [])
  let termOther = $derived(!catalog.term || manual.term || (form.term !== '' && form.term !== catalog.term.code))
  let subjectOther = $derived(!subjectGroups.groups.length || manual.subject || (form.subject !== '' && !subjectGroups.byCode.has(form.subject)))
  let courseOther = $derived(!courseList.length || manual.course || (form.catalog_nbr !== '' && !courseList.some((c) => c.nbr === form.catalog_nbr)))
  function pickTerm(e) { const v = e.currentTarget.value; manual.term = v === OTHER; if (v !== OTHER) form.term = v }
  function pickSubject(e) {
    const v = e.currentTarget.value
    manual.subject = v === OTHER
    if (v !== OTHER) { form.subject = v; form.catalog_nbr = ''; manual.course = false }
  }
  function pickCourse(e) { const v = e.currentTarget.value; manual.course = v === OTHER; if (v !== OTHER) form.catalog_nbr = v }

  let status = $derived(s?.status ?? 'idle')
  let signedIn = $derived(s?.signed_in ?? false)
  let tone = $derived(TONE[status])
  let busy = $derived(s?.busy ?? false)
  let running = $derived(status === 'monitoring' || status === 'starting')
  let limit = $derived(+(s?.config?.seat_limit ?? form.seat_limit) || 1)
  let countdown = $derived(
    s?.next_check ? Math.max(0, Math.round(s.next_check - (s.now + (ticker - pollAt) / 1000))) : null
  )
  let lastCheck = $derived(s?.last_check ? new Date(s.last_check * 1000).toLocaleTimeString('en-GB') : '—')
  let courseLabel = $derived(`${form.subject || '—'} ${form.catalog_nbr || ''}`.trim())
  let progress = $derived(
    s?.last_check && s?.next_check
      ? Math.min(1, Math.max(0, ((s.now + (ticker - pollAt) / 1000) - s.last_check) / Math.max(1, s.next_check - s.last_check)))
      : 0
  )
  let stops = $derived((s?.log ?? []).slice().reverse().slice(0, 6).map((l) => { const m = l.match(/^(\S+)\s{2}(.*)$/); return m ? { t: m[1], msg: m[2] } : { t: '', msg: l } }))
  let headline = $derived(HEAD[status])
</script>

<div class="shell" class:pop={isPopover}>
  <header>
    <h1>CAESAR Course Check</h1>
    <div class="head-right">
      {#if signedIn}
        <span class="bandstat"><span class="sdot on" aria-hidden="true"></span>Verified</span>
      {:else}
        <button class="bandbtn" onclick={signIn} disabled={busy} title="Open Chrome to solve the captcha">
          <span class="sdot" aria-hidden="true"></span>Not verified
        </button>
      {/if}
      {#if isPopover}<button class="bandbtn" onclick={quit} title="Quit CAESAR Course Check">Quit</button>{/if}
    </div>
  </header>

  <main>
    <section class="status {tone}" class:alert={status === 'alert'} aria-live="polite" aria-label="Monitor status">
      <div class="status-line">
        <span class="roundel" title="Course">{courseLabel}</span>
        <h2><span class="dot" class:pulse={status === 'monitoring'} aria-hidden="true"></span>{headline}</h2>
      </div>

        <div class="count">
          <strong>{s?.enrollment ?? 0}</strong>
          <span>{s?.capacity != null ? `of ${s.capacity} enrolled` : 'enrolled'}<br />{s?.available != null ? `${s.available} seat${s.available === 1 ? '' : 's'} open · ` : ''}alert below {limit}</span>
        </div>
        <div class="route" aria-hidden="true">
          <div class="track"><div class="done" style="width:{status === 'alert' ? 100 : progress * 100}%"></div></div>
          <span class="tick" style="left:25%"></span><span class="tick" style="left:50%"></span><span class="tick" style="left:75%"></span>
          <span class="stn a"></span>
          <span class="stn b" class:lit={status === 'alert'}></span>
          {#if status === 'monitoring'}<span class="train" style="left:{progress * 100}%"></span>{/if}
        </div>
        <div class="route-labels">
          <span><em>Last check</em>{lastCheck}</span>
          <span class="r"><em>{status === 'alert' ? 'Seat' : 'Next check'}</em>{status === 'alert' ? 'open' : (countdown !== null ? countdown + ' s' : '—')}</span>
        </div>
        {#if status !== 'monitoring' && status !== 'alert'}<p class="msg" title={s?.message}>{s?.message ?? 'Connecting…'}</p>{/if}
        {#if status === 'needs_signin'}<button class="btn primary solve" onclick={signIn} disabled={busy}>Solve captcha in Chrome</button>{/if}
    </section>

    <div class="tabs" role="tablist" aria-label="Settings and activity" tabindex="-1" onkeydown={onTabKey}>
      {#each TABS as [key, label]}
        <button role="tab" id={'tab-' + key} aria-selected={tab === key} aria-controls={'panel-' + key}
          tabindex={tab === key ? 0 : -1} class:active={tab === key} onclick={() => (tab = key)}>
          {label}{#if key === 'log' && s?.log?.length}<span class="n">{s.log.length}</span>{/if}
        </button>
      {/each}
      <button type="button" class="linkbtn tabend" onclick={testAlert}>Test alert</button>
    </div>

    {#if tab === 'course'}
      <form id="panel-course" role="tabpanel" aria-labelledby="tab-course" class="panel" onsubmit={(e) => { e.preventDefault(); if (!running && !busy) start() }}>
        <div class="grid">
          <label>Term
            {#if catalog.term && !termOther}
              <select name="term" value={form.term} onchange={pickTerm} disabled={busy}>
                <option value={catalog.term.code}>{catalog.term.name}</option>
                <option value={OTHER}>Other code…</option>
              </select>
            {:else}
              <input name="term" bind:value={form.term} oninput={() => (manual.term = true)} disabled={busy} inputmode="numeric" autocomplete="off" spellcheck="false" placeholder="5050…" />
            {/if}
          </label>
          <label>Subject
            {#if !subjectOther}
              <select name="subject" value={form.subject} onchange={pickSubject} disabled={busy}>
                {#if !form.subject}<option value="" disabled>Choose…</option>{/if}
                {#each subjectGroups.groups as g}
                  <optgroup label={g.school}>
                    {#each g.items as sub}<option value={sub.code}>{sub.code} · {sub.name}</option>{/each}
                  </optgroup>
                {/each}
                <option value={OTHER}>Other…</option>
              </select>
            {:else}
              <input name="subject" bind:value={form.subject} oninput={() => (manual.subject = true)} disabled={busy} autocomplete="off" spellcheck="false" placeholder="COMP_SCI…" />
            {/if}
          </label>
          <label class="wide">Course
            {#if !courseOther}
              <select name="catalog_nbr" value={form.catalog_nbr} onchange={pickCourse} disabled={busy}>
                {#if !form.catalog_nbr}<option value="" disabled>Choose…</option>{/if}
                {#each courseList as c}<option value={c.nbr}>{c.nbr} · {c.name}</option>{/each}
                <option value={OTHER}>Other…</option>
              </select>
            {:else}
              <input name="catalog_nbr" bind:value={form.catalog_nbr} oninput={() => (manual.course = true)} disabled={busy} autocomplete="off" spellcheck="false" placeholder="340-0…" />
            {/if}
          </label>
          <label>Alert below
            <input name="seat_limit" type="number" inputmode="numeric" min="1" bind:value={form.seat_limit} disabled={busy} autocomplete="off" />
          </label>
          <label>Every (s)
            <input name="interval" type="number" inputmode="numeric" min="10" bind:value={form.interval} disabled={busy} autocomplete="off" />
          </label>
        </div>
      </form>
    {:else}
      <div id="panel-log" role="tabpanel" aria-labelledby="tab-log" class="panel">
        {#if stops.length}
          <ol class="stops">
            {#each stops as st}<li><time>{st.t}</time><span>{st.msg}</span></li>{/each}
          </ol>
        {:else}<p class="note">No stops yet. Every check shows up here.</p>{/if}
      </div>
    {/if}

    {#if err}<p class="err" role="alert" title={err}>{err}</p>{/if}
  </main>

  <footer>
    {#if running}
      <button class="btn stop" onclick={stop}>Stop monitoring</button>
    {:else if status === 'alert'}
      <button class="btn primary" onclick={openCaesar}>Open CAESAR</button>
      <button class="btn ghost" onclick={start} disabled={busy}>Monitor again</button>
    {:else}
      <button class="btn primary" onclick={start} disabled={busy}>Start monitoring</button>
    {/if}
  </footer>
</div>

<style>
  .shell { min-height: 100vh; display: flex; flex-direction: column; max-width: 560px; margin: 0 auto; }
  .shell.pop { height: 100vh; min-height: 0; max-width: none; }
  header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: 0 var(--space-3) 0 var(--space-4); height: 44px; flex: none; background: var(--band); color: var(--on-band); }
  h1 { font-size: 14px; font-weight: 700; margin: 0; letter-spacing: .005em; white-space: nowrap; }
  .head-right { display: flex; align-items: center; gap: 2px; }
  .bandstat { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: color-mix(in srgb, var(--on-band) 82%, transparent); padding: 4px 7px; }
  .bandbtn { display: inline-flex; align-items: center; gap: 6px; font: inherit; font-size: 12px; color: color-mix(in srgb, var(--on-band) 82%, transparent); background: none; border: 0; border-radius: var(--radius); padding: 4px 7px; cursor: pointer; transition: background-color var(--dur) var(--ease-out), color var(--dur) var(--ease-out); }
  .bandbtn:hover:not(:disabled) { color: var(--on-band); background: color-mix(in srgb, #fff 16%, transparent); }
  .bandbtn:disabled { opacity: .6; cursor: not-allowed; }
  .bandbtn:focus-visible { outline: 2px solid #fff; outline-offset: 1px; }
  .sdot { width: 7px; height: 7px; border-radius: 50%; border: 1.5px solid #fff; } .sdot.on { background: #fff; }

  main { flex: 1; min-height: 0; overflow: hidden; padding: var(--space-3) var(--space-4) var(--space-2); display: flex; flex-direction: column; gap: var(--space-2); }

  .status { --tone: var(--text-muted); }
  .status.ok { --tone: var(--ok); } .status.warn { --tone: var(--warn); } .status.bad { --tone: var(--bad); }
  .status-line { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
  h2 { display: flex; align-items: center; gap: 8px; font-size: 15px; font-weight: 700; margin: 0; color: var(--text); }
  .roundel { font: 700 12px/1 var(--font-sans); letter-spacing: .02em; color: var(--on-accent); background: var(--accent); border-radius: 999px; padding: 6px 12px; white-space: nowrap; }
  .dot { position: relative; width: 9px; height: 9px; border-radius: 50%; background: var(--tone); flex: none; }
  .dot.pulse::after { content: ''; position: absolute; inset: 0; border-radius: 50%; background: var(--tone); animation: ping 2s var(--ease-out) infinite; }
  @keyframes ping { 0% { transform: scale(1); opacity: .5; } 80%, 100% { transform: scale(2.8); opacity: 0; } }
  .msg, .err { display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .msg { margin: var(--space-1) 0 var(--space-2); color: var(--text-muted); font-size: 12px; text-wrap: pretty; overflow-wrap: anywhere; }
  .count { display: flex; align-items: flex-end; gap: var(--space-3); margin-top: var(--space-1); }
  .count strong { font: 700 40px/0.9 var(--font-sans); letter-spacing: -.035em; font-variant-numeric: tabular-nums; }
  .count span { color: var(--text-muted); font-size: 12px; line-height: 1.3; padding-bottom: 2px; }

  /* Signature move: route strip. The train is the time since the last check. */
  .route { position: relative; height: 18px; margin: var(--space-2) 6px 0; }
  .track { position: absolute; left: 0; right: 0; top: 7px; height: 4px; background: var(--rule); border-radius: 2px; overflow: hidden; }
  .done { height: 100%; background: var(--accent); }
  .stn { position: absolute; top: 3px; width: 12px; height: 12px; border-radius: 50%; background: var(--bg); border: 3px solid var(--accent); }
  .stn.a { left: -6px; } .stn.b { right: -6px; }
  .tick { position: absolute; top: 5px; width: 2px; height: 8px; margin-left: -1px; background: var(--rule); border-radius: 1px; }
  .stn.lit { top: -1px; right: -10px; width: 20px; height: 20px; background: var(--ok); border-color: var(--ok); box-shadow: 0 0 0 4px color-mix(in srgb, var(--ok) 30%, transparent); animation: arrive 520ms var(--ease-out) both; }
  @keyframes arrive { from { transform: scale(.3); opacity: 0; } to { transform: scale(1); opacity: 1; } }
  .status.alert .count strong { color: var(--ok); }
  .status.alert .done { background: var(--ok); }
  .train { position: absolute; top: 4px; width: 10px; height: 10px; margin-left: -5px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 3px var(--bg); transition: left 1s linear; }
  .route-labels { display: flex; justify-content: space-between; margin-top: 2px; font: 500 12px var(--font-mono); font-variant-numeric: tabular-nums; }
  .route-labels em { display: block; font: 500 11px var(--font-sans); font-style: normal; color: var(--text-muted); }
  .route-labels .r { text-align: right; }

  .tabs { display: flex; gap: var(--space-4); border-bottom: 2px solid var(--rule); flex: none; }
  .tabs button { display: inline-flex; align-items: center; gap: 6px; font: inherit; font-weight: 700; color: var(--text-muted); background: none; border: 0; border-bottom: 3px solid transparent; margin-bottom: -2px; padding: 4px 0 7px; cursor: pointer; transition: color var(--dur) var(--ease-out), border-color var(--dur) var(--ease-out); }
  .tabs button:hover { color: var(--text); }
  .tabs button.active { color: var(--text); border-color: var(--accent); }
  .tabs button:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; border-radius: 2px; }
  .n { font: 600 11px var(--font-mono); color: var(--on-accent); background: var(--accent); border-radius: 999px; padding: 0 6px; }

  .panel { min-height: 0; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-2) var(--space-3); }
  label { display: grid; gap: 3px; min-width: 0; font-size: 11px; font-weight: 600; color: var(--text-muted); }
  input {
    min-width: 0; font: inherit; font-size: 13px; font-weight: 500; color: var(--text); background: var(--sunken); border: 1px solid transparent; border-bottom-color: var(--text-muted);
    border-radius: var(--radius) var(--radius) 0 0; padding: 0 8px; height: var(--field-h); user-select: text; -webkit-user-select: text; cursor: text; font-variant-numeric: tabular-nums;
    transition: border-color var(--dur) var(--ease-out), background-color var(--dur) var(--ease-out);
  }
  select {
    min-width: 0; width: 100%; font: inherit; font-size: 13px; font-weight: 500; color: var(--text); background: var(--sunken); border: 1px solid transparent; border-bottom-color: var(--text-muted);
    border-radius: var(--radius) var(--radius) 0 0; padding: 0 6px; height: var(--field-h); cursor: pointer; text-overflow: ellipsis;
    transition: border-color var(--dur) var(--ease-out), background-color var(--dur) var(--ease-out);
  }
  select:hover:not(:disabled) { background: color-mix(in srgb, var(--accent) 8%, var(--sunken)); }
  select:focus-visible { outline: none; border-bottom: 2px solid var(--focus); background: var(--bg); box-shadow: 0 0 0 1px var(--rule); }
  select:disabled { cursor: not-allowed; background: transparent; border-bottom-style: dashed; }
  .wide { grid-column: 1 / -1; }
  input::placeholder { color: var(--text-muted); font-weight: 400; }
  input:hover:not(:disabled) { background: color-mix(in srgb, var(--accent) 8%, var(--sunken)); }
  input:focus-visible { outline: none; border-bottom: 2px solid var(--focus); background: var(--bg); box-shadow: 0 0 0 1px var(--rule); }
  input:disabled { cursor: not-allowed; background: transparent; border-bottom-style: dashed; color: var(--text); }
  .tabend { margin: 0 0 6px auto !important; }
  .linkbtn { margin-top: var(--space-2); font: inherit; font-size: 12px; font-weight: 600; color: var(--accent); background: none; border: 0; padding: 2px 0; cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
  .linkbtn:hover { color: var(--accent-hover); }
  .linkbtn:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; border-radius: 2px; }
  .note { margin: var(--space-2) 0 0; font-size: 12px; color: var(--text-muted); }
  .err { margin: 0; color: var(--bad); font-weight: 600; font-size: 12px; }

  /* Activity as a line of stops */
  .stops { list-style: none; margin: 0; padding: 0 0 0 14px; position: relative; user-select: text; -webkit-user-select: text; cursor: text; }
  .stops::before { content: ''; position: absolute; left: 4px; top: 12px; bottom: 12px; width: 3px; background: var(--accent); border-radius: 2px; }
  .stops li { position: relative; display: flex; gap: var(--space-3); padding: 3px 0; font-size: 12px; }
  .stops li::before { content: ''; position: absolute; left: -14px; top: 8px; width: 7px; height: 7px; border-radius: 50%; background: var(--bg); border: 2px solid var(--accent); box-sizing: content-box; margin-left: -1px; }
  .stops time { font: 500 11px/1.7 var(--font-mono); color: var(--text-muted); flex: none; font-variant-numeric: tabular-nums; }
  .stops span { overflow-wrap: anywhere; }

  .btn { display: inline-flex; align-items: center; justify-content: center; font: inherit; font-weight: 700; min-height: var(--btn-h); padding: 0 16px; border-radius: var(--radius); border: 0; cursor: pointer; transition: background-color var(--dur) var(--ease-out), transform 100ms var(--ease-out), filter var(--dur) var(--ease-out); }
  .solve { margin-top: var(--space-1); width: 100%; }
  .btn:active:not(:disabled) { transform: translateY(1px); }
  .btn:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
  .btn:disabled { opacity: .4; cursor: not-allowed; }
  .primary { background: var(--accent); color: var(--on-accent); } .primary:hover:not(:disabled) { background: var(--accent-hover); }
  .stop, .ghost { background: transparent; color: var(--text); box-shadow: inset 0 0 0 1.5px var(--text-muted); }
  .stop:hover, .ghost:hover:not(:disabled) { background: var(--sunken); }

  footer { padding: var(--space-3) var(--space-4) var(--space-3); border-top: 2px solid var(--rule); flex: none; }
  footer { display: flex; gap: var(--space-2); }
  footer .btn { flex: 1; }

  @media (prefers-reduced-motion: reduce) {
    .dot.pulse::after, .stn.lit { animation: none; }
    .train, .btn, input, select, .tabs button, .bandbtn { transition: none; }
  }
</style>
