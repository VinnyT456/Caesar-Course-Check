<script>
  import { onMount, onDestroy } from 'svelte'
  import { api } from './api.js'
  import Combo from './Combo.svelte'

  const blank = () => ({ term: '', school: '', subject: '', catalog_nbr: '', class_nbr: '', seat_limit: 0 })
  let s = $state(null)
  let form = $state({ classes: [blank()], interval: 60, after_alert: 'stop', quiet_on: false, quiet_start: '23:00', quiet_end: '07:00', sound: 'beep', volume: 60 })
  let sel = $state(0)
  let formLoaded = false
  const OTHER = '__other'
  const MAX = 5
  let catalog = $state({ term: null, schools: [] })
  let manual = $state({ term: false, subject: false, course: false })
  let err = $state('')
  let note = $state('')
  let noteTimer
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
  const TABS = [['course', 'Class'], ['alerts', 'Alerts'], ['time', 'Schedule']]
  const EVERY = [[30, '30 s'], [60, '1 min'], [120, '2 min'], [300, '5 min']]
  const AFTER = [['stop', 'Stop', 'Stop monitoring after the first alert'], ['keep', 'Keep going', 'Keep checking after an alert'], ['repeat', 'Re-alert', 'Alert again every 5 minutes until you open CAESAR or stop']]
  const SOUNDS = [['beep', 'Beep'], ['chime', 'Chime'], ['bell', 'Bell'], ['off', 'Off']]
  // [frequency Hz, start s, length s]
  const TONES = { beep: [[880, 0, .2], [880, .25, .2], [880, .5, .2]], chime: [[784, 0, .35], [1175, .3, .6]], bell: [[523, 0, 1.3], [784, 0, .9], [1046, 0, .6]] }

  let cur = $derived(form.classes[sel] ?? form.classes[0])
  const label = (c) => `${c.subject} ${c.catalog_nbr}`.trim() || 'New class'

  async function poll() {
    try {
      s = await api('/api/state')
      pollAt = Date.now()
      if ((s.sections?.text ?? '') !== secText) { secText = s.sections?.text ?? ''; secFrom = Date.now() }
      err = ''
      if (!formLoaded) { form = { ...form, ...s.config }; formLoaded = true }
      else if (s.busy) {  // the checker pulls a threshold above the class size down to the capacity
        s.config.classes.forEach((c, i) => { if (form.classes[i] && c.seat_limit < form.classes[i].seat_limit) form.classes[i].seat_limit = c.seat_limit })
      }
      if (s.alert_id > lastAlert) {
        if (lastAlert !== 0 || s.status === 'alert') play()
        lastAlert = s.alert_id
        const open = s.classes.findIndex((c) => c.open)
        if (open >= 0) sel = open
      }
    } catch { err = 'Lost connection to the app backend.' }
  }

  function unlockAudio() {
    // WebKit only allows audio after a user gesture: create/resume the context on click.
    try { audio ??= new AudioContext(); audio.resume() } catch {}
  }
  function play(kind = form.sound) {
    if (kind === 'off') return
    try {
      unlockAudio()
      const ctx = audio, peak = 0.3 * (form.volume / 100)
      for (const [f, at, len] of TONES[kind] ?? TONES.beep) {
        const o = ctx.createOscillator(), g = ctx.createGain(), t = ctx.currentTime + at
        o.frequency.value = f; o.connect(g); g.connect(ctx.destination)
        g.gain.setValueAtTime(Math.max(peak, 0.0002), t)
        g.gain.exponentialRampToValueAtTime(0.0001, t + len)
        o.start(t); o.stop(t + len + 0.02)
      }
    } catch {}
  }

  async function signIn(e) { try { await api('/api/signin', { trusted: e?.isTrusted, detail: e?.detail, type: e?.type, pointer: e?.pointerType, x: e?.clientX, y: e?.clientY, vis: document.visibilityState, focus: document.hasFocus() }); poll() } catch (e) { err = e.message } }
  async function start() {
    unlockAudio()
    const bad = form.classes.find((c) => !c.subject || !c.catalog_nbr)
    if (bad) { sel = form.classes.indexOf(bad); tab = 'course'; err = `Pick a subject and course for ${label(bad) === 'New class' ? 'the new class' : label(bad)}.`; return }
    try {
      await api('/api/start', { ...form, classes: form.classes.map((c) => ({ ...c, seat_limit: +c.seat_limit || 0 })), interval: +form.interval, volume: +form.volume })
      poll()
    } catch (e) { err = 'Check the class fields: ' + e.message }
  }
  async function quit() { try { await api('/api/app/quit', {}) } catch {} }
  async function testAlert() { try { await api('/api/app/test-alert', {}) } catch (e) { err = e.message } }
  async function openCaesar() {
    try {
      const r = await api('/api/app/caesar', {})
      if (r.copied) { note = `Copied ${r.copied}. Paste it into CAESAR.`; clearTimeout(noteTimer); noteTimer = setTimeout(() => (note = ''), 8000) }
      poll()
    } catch (e) { err = e.message }
  }
  async function stop() { try { await api('/api/stop', {}); poll() } catch (e) { err = e.message } }

  function onTabKey(e) {
    const i = TABS.findIndex(([k]) => k === tab)
    const n = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : null
    if (n === null) return
    tab = TABS[(n + TABS.length) % TABS.length][0]
    document.getElementById('tab-' + tab)?.focus()
  }

  function pick(i) { sel = i; manual = { term: false, subject: false, course: false } }
  function addClass() {
    if (form.classes.length >= MAX) return
    form.classes.push({ ...cur, catalog_nbr: '', class_nbr: '', seat_limit: 0 })
    pick(form.classes.length - 1)
    tab = 'course'
  }
  function removeClass() {
    if (form.classes.length < 2) return
    form.classes.splice(sel, 1)
    pick(Math.min(sel, form.classes.length - 1))
  }
  function bump(d) { cur.seat_limit = Math.max(1, (+cur.seat_limit || cs?.capacity || 1) + d) }
  function setLimit(e) { cur.seat_limit = Math.max(0, parseInt(e.currentTarget.value) || 0) }

  async function loadCatalog() {
    try { catalog = await api('/api/catalog') } catch { /* dropdowns fall back to typing */ }
  }
  onMount(() => { loadCatalog(); poll(); timer = setInterval(() => { poll(); ticker = Date.now() }, 1500) })
  onDestroy(() => clearInterval(timer))

  // Every school keeps its own subjects: a code such as CHEM can exist in more than one school, with different courses.
  const SCHOOL = { 'Pritzker School of Law': 'Law', 'School of Professional Studies': 'SPS (undergrad & grad)', 'McCormick School of Engineering and Applied Science': 'McCormick School of Engineering', 'Weinberg College of Arts and Sciences': 'Weinberg College of Arts & Sciences' }
  const byNbr = (a, b) => a.nbr.localeCompare(b.nbr, undefined, { numeric: true })
  let subjectGroups = $derived.by(() => {
    const byKey = new Map(), byCode = new Map(), groups = []
    for (const sc of catalog.schools) {
      const items = sc.subjects.map((sub) => ({ ...sub, school: sc.name, courses: [...sub.courses].sort(byNbr) }))
      for (const e of items) {
        byKey.set(`${sc.name}|${e.code}`, e)
        const have = byCode.get(e.code)
        if (!have || e.courses.length > have.courses.length) byCode.set(e.code, e)  // no school chosen yet: use the fullest one
      }
      if (items.length) groups.push({ school: SCHOOL[sc.name] ?? sc.name, items })
    }
    return { groups, byKey, byCode }
  })
  let curSubject = $derived(subjectGroups.byKey.get(`${cur.school}|${cur.subject}`) ?? subjectGroups.byCode.get(cur.subject))
  let subjectItems = $derived(subjectGroups.groups.flatMap((g) => g.items.map((x) => ({ value: `${x.school}|${x.code}`, label: `${x.code} · ${x.name}`, group: g.school }))))
  let courseList = $derived(curSubject?.courses ?? [])
  let courseItems = $derived(courseList.map((c) => ({ value: c.nbr, label: `${c.nbr} · ${c.name}` })))
  let termOther = $derived(!catalog.term || manual.term || (cur.term !== '' && cur.term !== catalog.term.code))
  let subjectOther = $derived(!subjectGroups.groups.length || manual.subject || (cur.subject !== '' && !curSubject))
  let courseOther = $derived(!courseList.length || manual.course || (cur.catalog_nbr !== '' && !courseList.some((c) => c.nbr === cur.catalog_nbr)))
  function pickTerm(e) { const v = e.currentTarget.value; manual.term = v === OTHER; if (v !== OTHER) cur.term = v }
  function pickSubject(v) {
    manual.subject = v === OTHER
    if (v !== OTHER) { const [school, code] = v.split('|'); cur.school = school; cur.subject = code; cur.catalog_nbr = ''; cur.class_nbr = ''; cur.seat_limit = 0; manual.course = false }
  }
  function pickCourse(v) { manual.course = v === OTHER; cur.class_nbr = ''; cur.seat_limit = 0; if (v !== OTHER) cur.catalog_nbr = v }
  let sectionList = $derived(courseList.find((c) => c.nbr === cur.catalog_nbr)?.sections ?? [])
  // Every section CAESAR lists for a course (lectures, discussions, labs), loaded on demand.
  let loaded = $state({})
  let loadingSec = $state(false)
  let secFrom = $state(0)
  let secText = ''
  // The server reports real stages; between them the bar creeps so a slow CAESAR never looks frozen.
  let secPct = $derived.by(() => {
    if (!loadingSec) return 0
    const base = s?.sections?.pct ?? 4
    return Math.min(97, base + Math.min(26, Math.max(0, (ticker - secFrom) / 1000) * 1.1))
  })
  let secLabel = $derived(loadingSec ? (s?.sections?.text ?? 'Contacting the app') : '')
  let secErr = $state('')
  const secKey = (c) => `${c.term}|${c.subject}|${c.catalog_nbr}`
  const COMP = { LEC: 'Lectures', DIS: 'Discussions', LAB: 'Labs', SEM: 'Seminars', IND: 'Independent study' }
  const RANK = ['LEC', 'DIS', 'LAB', 'SEM']
  let loadedRows = $derived(loaded[secKey(cur)] ?? null)
  let sectionItems = $derived.by(() => {
    if (!loadedRows) return []
    const rank = (r) => { const i = RANK.indexOf(r.comp); return i < 0 ? RANK.length : i }
    const rows = loadedRows.map((r, i) => ({ r, i })).sort((a, b) => rank(a.r) - rank(b.r) || a.i - b.i).map((x) => x.r)
    const items = rows.map((r) => ({ value: r.id, group: COMP[r.comp] ?? (r.comp || 'Other'), label: [r.sec, r.when !== 'TBA' ? r.when.replace(' - ', '–') : '', r.who, '#' + r.id].filter(Boolean).join(' · ') }))
    return [{ value: '', label: 'Any section' }, ...items]
  })
  async function loadSections() {
    if (loadingSec || !cur.subject || !cur.catalog_nbr) return
    loadingSec = true; secErr = ''; secFrom = Date.now()
    try {
      const r = await api('/api/sections', { term: cur.term, subject: cur.subject, catalog_nbr: cur.catalog_nbr })
      if (!r.ok) secErr = r.error
      else if (!r.sections.length) secErr = 'CAESAR listed no sections for this course.'
      else loaded[secKey(cur)] = r.sections
    } catch (e) { secErr = e.message } finally { loadingSec = false }
  }
  const DAY = { Monday: 'Mon', Tuesday: 'Tue', Wednesday: 'Wed', Thursday: 'Thu', Friday: 'Fri', Saturday: 'Sat', Sunday: 'Sun' }
  function sectionLabel(x) {
    const when = x.days?.length ? `${x.days.map((d) => DAY[d] ?? d).join('/')} ${x.start ?? ''}${x.end ? '–' + x.end : ''}` : 'Time TBA'
    return `Sec ${x.sec} · ${when}${x.who?.length ? ' · ' + x.who.join(', ') : ''}`
  }

  let status = $derived(s?.status ?? 'idle')
  let signedIn = $derived(s?.signed_in ?? false)
  let tone = $derived(TONE[status])
  let busy = $derived(s?.busy ?? false)
  let running = $derived(status === 'monitoring' || status === 'starting')
  let cs = $derived(s?.classes?.[sel])
  let hasData = $derived(cs?.enrollment != null)
  let limit = $derived(+cur.seat_limit || cs?.capacity || null)
  let now = $derived(s ? s.now + (ticker - pollAt) / 1000 : 0)
  let countdown = $derived(s?.next_check ? Math.max(0, Math.round(s.next_check - now)) : null)
  let lastCheck = $derived(s?.last_check ? new Date(s.last_check * 1000).toLocaleTimeString('en-GB') : '—')
  let resumes = $derived(s?.quiet_until ? new Date(s.quiet_until * 1000).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : null)
  let progress = $derived(s?.last_check && s?.next_check ? Math.min(1, Math.max(0, (now - s.last_check) / Math.max(1, s.next_check - s.last_check))) : 0)
  let showMsg = $derived(status === 'monitoring' ? !!s?.quiet_until : status !== 'alert' && status !== 'needs_signin' && !!s?.message && !s.message.startsWith('Ready'))
  let headline = $derived(HEAD[status])
  // Before the first check there is nothing to chart: say what to do instead of showing an empty gauge.
  let showRoute = $derived(hasData || status === 'monitoring' || status === 'alert')
  let idleHint = $derived(status !== 'idle' ? '' : signedIn
    ? 'Pick a class, then press Start. You get an alert the moment a seat opens.'
    : 'First time: Start opens Chrome once to solve the captcha. Monitoring then begins by itself.')
  let limitHint = $derived(!cur.seat_limit ? 'Alerts as soon as any seat opens.' : `Alerts when fewer than ${cur.seat_limit} are enrolled.`)
  let spark = $derived.by(() => {
    const h = cs?.history ?? []
    if (h.length < 2) return null
    const ys = h.map((p) => p[1]), lo = Math.min(...ys), hi = Math.max(...ys)
    const W = 88, H = 26, pts = h.map((p, i) => [(i / (h.length - 1)) * W, hi === lo ? H / 2 : H - 2 - ((p[1] - lo) / (hi - lo)) * (H - 4)])
    return { d: pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' '), end: pts[pts.length - 1], W, H }
  })
</script>

<div class="shell" class:pop={isPopover}>
  <header>
    <h1>CAESAR Course Check</h1>
    <div class="head-right">
      {#if signedIn}
        <span class="bandstat"><span class="sdot on" aria-hidden="true"></span>Verified</span>
      {:else}
        <button class="bandbtn" onclick={signIn} disabled={busy} title="Open Chrome to solve the captcha once">
          <span class="sdot" aria-hidden="true"></span>Not verified
        </button>
      {/if}
      {#if isPopover}<button class="bandbtn" onclick={quit} title="Quit CAESAR Course Check">Quit</button>{/if}
    </div>
  </header>

  <main>
    <section class="status {tone}" class:alert={status === 'alert'} aria-live="polite" aria-label="Monitor status">
      <div class="status-line">
        <span class="roundel" title="Class">{label(cur)}</span>
        <h2><span class="dot" aria-hidden="true"></span>{headline}</h2>
      </div>

      {#if showRoute}
      <div class="count">
        <strong class:none={!hasData}>{hasData ? cs.enrollment : '—'}</strong>
        {#if hasData}
          <span class="sub">{cs.capacity != null ? `of ${cs.capacity} enrolled` : 'enrolled'}<br />{cs.available != null ? `${cs.available} open` : ''}{cs.waitlist ? `${cs.available != null ? ' · ' : ''}${cs.waitlist} waitlisted` : ''}{cur.seat_limit && cur.seat_limit !== cs.capacity ? `${cs.available != null || cs.waitlist ? ' · ' : ''}alert below ${cur.seat_limit}` : ''}</span>
        {/if}
        {#if spark}
          <svg class="spark" viewBox="0 0 {spark.W} {spark.H}" width={spark.W} height={spark.H} role="img" aria-label="Enrollment at recent checks">
            <path d={spark.d} fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" />
            <circle cx={spark.end[0]} cy={spark.end[1]} r="2.5" fill="var(--accent)" />
          </svg>
        {/if}
      </div>
      <div class="route" aria-hidden="true">
        <div class="track"><div class="done" style="width:{status === 'alert' ? 100 : progress * 100}%"></div></div>
        <span class="stn a"></span>
        <span class="stn b" class:lit={status === 'alert'}></span>
        {#if status === 'monitoring' && !resumes}<span class="train" style="left:{progress * 100}%"></span>{/if}
      </div>
      <div class="route-labels">
        <span><em>Last check</em>{lastCheck}</span>
        <span class="r"><em>{status === 'alert' ? 'Seat' : resumes ? 'Resumes' : 'Next check'}</em>{status === 'alert' ? 'open' : resumes ?? (countdown !== null ? countdown + ' s' : '—')}</span>
      </div>
      {/if}
      {#if idleHint}<p class="msg hintline">{idleHint}</p>{:else if showMsg}<p class="msg" title={s?.message}>{s?.message}</p>{/if}
    </section>

    <div class="tabs" role="tablist" aria-label="Settings" tabindex="-1" onkeydown={onTabKey}>
      {#each TABS as [key, name]}
        <button role="tab" id={'tab-' + key} aria-selected={tab === key} aria-controls={'panel-' + key}
          tabindex={tab === key ? 0 : -1} class:active={tab === key} onclick={() => (tab = key)}>{name}</button>
      {/each}
    </div>

    {#if tab === 'course'}
      <form id="panel-course" role="tabpanel" aria-labelledby="tab-course" class="panel" onsubmit={(e) => { e.preventDefault(); if (!busy) start() }}>
        {#if form.classes.length > 1}
        <div class="chips" role="group" aria-label="Watched classes">
          {#each form.classes as c, i}
            <button type="button" class="chip" class:on={i === sel} aria-pressed={i === sel} onclick={() => pick(i)} title={label(c)}>
              {#if s?.classes?.[i]?.open}<span class="cdot" aria-label="Seat open"></span>{/if}<span class="ct">{form.classes.length > 3 && c.catalog_nbr ? c.catalog_nbr : label(c)}</span>
            </button>
          {/each}
          {#if form.classes.length < MAX && !busy}<button type="button" class="chip add" onclick={addClass} aria-label="Watch another class" title="Watch another class">+</button>{/if}
          {#if form.classes.length > 1 && !busy}<button type="button" class="chip add" onclick={removeClass} aria-label="Remove this class" title="Remove this class">−</button>{/if}
        </div>
        {/if}
        <div class="grid">
          <label>Term
            {#if catalog.term && !termOther}
              <select name="term" value={cur.term} onchange={pickTerm} disabled={busy}>
                <option value={catalog.term.code}>{catalog.term.name}</option>
                <option value={OTHER}>Other code…</option>
              </select>
            {:else}
              <input name="term" bind:value={form.classes[sel].term} oninput={() => (manual.term = true)} disabled={busy} inputmode="numeric" autocomplete="off" spellcheck="false" placeholder="5050…" />
            {/if}
          </label>
          <label>Subject
            {#if !subjectOther}
              <Combo name="subject" value={curSubject ? `${curSubject.school}|${curSubject.code}` : cur.subject} items={subjectItems} placeholder="Search subjects…" disabled={busy} extra={{ value: OTHER, label: 'Other…' }} onpick={pickSubject} />
            {:else}
              <input name="subject" bind:value={form.classes[sel].subject} oninput={() => (manual.subject = true)} disabled={busy} autocomplete="off" spellcheck="false" placeholder="COMP_SCI…" />
            {/if}
          </label>
          <label class="wide">Course
            {#if !courseOther}
              <Combo name="catalog_nbr" value={cur.catalog_nbr} items={courseItems} placeholder="Search courses…" disabled={busy} extra={{ value: OTHER, label: 'Other…' }} onpick={pickCourse} />
            {:else}
              <input name="catalog_nbr" bind:value={form.classes[sel].catalog_nbr} oninput={() => (manual.course = true)} disabled={busy} autocomplete="off" spellcheck="false" placeholder="340-0…" />
            {/if}
          </label>
          <div class="wide field">
            <div class="fhead">
              <span id="l-section">Section</span>
              {#if cur.subject && cur.catalog_nbr && !busy}
                <button type="button" class="linkbtn tiny" onclick={loadSections} disabled={loadingSec}>{loadingSec ? 'Loading…' : loadedRows ? 'Reload' : 'Load discussions & labs'}</button>
              {/if}
            </div>
            {#if loadingSec}
              <div class="prog" role="progressbar" aria-label="Loading sections" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(secPct)}>
                <div class="bar"><div class="fill" style="width:{secPct}%"></div></div>
                <span class="plabel">{secLabel}…</span>
              </div>
            {:else if loadedRows}
              <Combo up name="class_nbr" value={cur.class_nbr} items={sectionItems} placeholder="Search sections…" disabled={busy} onpick={(v) => { cur.class_nbr = v; cur.seat_limit = 0 }} />
            {:else if sectionList.length && !courseOther}
              <select name="class_nbr" aria-labelledby="l-section" bind:value={form.classes[sel].class_nbr} onchange={() => (cur.seat_limit = 0)} disabled={busy}>
                <option value="">Any section</option>
                {#each sectionList as x}<option value={x.id}>{sectionLabel(x)}</option>{/each}
              </select>
            {:else}
              <input name="class_nbr" aria-labelledby="l-section" bind:value={form.classes[sel].class_nbr} disabled={busy} inputmode="numeric" autocomplete="off" spellcheck="false" placeholder="Class number (optional)" />
            {/if}
            {#if secErr}<span class="ferr" title={secErr}>{secErr}</span>{/if}
          </div>
        </div>
        {#if form.classes.length === 1 && !busy}<button type="button" class="linkbtn addlink" onclick={addClass}>+ Watch another class</button>{/if}
      </form>
    {:else if tab === 'alerts'}
      <form id="panel-alerts" role="tabpanel" aria-labelledby="tab-alerts" class="panel opts" onsubmit={(e) => { e.preventDefault(); if (!busy) start() }}>
        <div class="opt inline">
          <span class="opt-l" id="l-limit">Alert below</span>
          <div class="stepper" role="group" aria-labelledby="l-limit">
            <button type="button" aria-label="Decrease" onclick={() => bump(-1)} disabled={busy || (cur.seat_limit || cs?.capacity || 1) <= 1}>−</button>
            <input name="seat_limit" type="number" inputmode="numeric" min="1" value={cur.seat_limit || ''} oninput={setLimit} placeholder={cs?.capacity != null ? String(cs.capacity) : '—'} disabled={busy} autocomplete="off" />
            <button type="button" aria-label="Increase" onclick={() => bump(1)} disabled={busy}>+</button>
          </div>
          {#if cur.seat_limit}<button type="button" class="linkbtn auto" onclick={() => (cur.seat_limit = 0)} disabled={busy} title="Alert when any seat opens (the class capacity)">Auto</button>{:else}<span class="of">Auto</span>{/if}
        </div>
        <p class="hint under">{limitHint}</p>
        <div class="opt inline">
          <span class="opt-l" id="l-after">After alert</span>
          <div class="seg" role="radiogroup" aria-labelledby="l-after">
            {#each AFTER as [v, l, tip]}
              <button type="button" role="radio" aria-checked={form.after_alert === v} class:on={form.after_alert === v} disabled={busy} title={tip} onclick={() => (form.after_alert = v)}>{l}</button>
            {/each}
          </div>
        </div>
        <div class="opt inline">
          <span class="opt-l" id="l-sound">Sound</span>
          <div class="seg" role="radiogroup" aria-labelledby="l-sound">
            {#each SOUNDS as [v, l]}
              <button type="button" role="radio" aria-checked={form.sound === v} class:on={form.sound === v} disabled={busy} onclick={() => { form.sound = v; play(v) }}>{l}</button>
            {/each}
          </div>
        </div>
        <div class="opt inline">
          <label class="opt-l" for="vol">Volume</label>
          <input id="vol" class="range" type="range" min="0" max="100" step="10" bind:value={form.volume} disabled={busy || form.sound === 'off'} onchange={() => play()} />
        </div>
        <button type="button" class="linkbtn" onclick={testAlert}>Send a test notification</button>
      </form>
    {:else}
      <form id="panel-time" role="tabpanel" aria-labelledby="tab-time" class="panel opts" onsubmit={(e) => { e.preventDefault(); if (!busy) start() }}>
        <div class="opt">
          <span class="opt-l" id="l-every">Check every</span>
          <div class="seg" role="radiogroup" aria-labelledby="l-every">
            {#each EVERY as [v, l]}
              <button type="button" role="radio" aria-checked={+form.interval === v} class:on={+form.interval === v} disabled={busy} onclick={() => (form.interval = v)}>{l}</button>
            {/each}
          </div>
        </div>
        <div class="opt">
          <label class="check"><input type="checkbox" bind:checked={form.quiet_on} disabled={busy} />Pause checks overnight</label>
          <div class="when">
            <input type="time" aria-label="Pause from" bind:value={form.quiet_start} disabled={busy || !form.quiet_on} />
            <span>to</span>
            <input type="time" aria-label="Resume at" bind:value={form.quiet_end} disabled={busy || !form.quiet_on} />
          </div>
        </div>
      </form>
    {/if}

    {#if err}<p class="err" role="alert" title={err}>{err}</p>{:else if note}<p class="okmsg" role="status">{note}</p>{:else if running}<p class="hint lock">Stop monitoring to change settings.</p>{/if}
  </main>

  <footer>
    {#if status === 'alert'}
      <button class="btn primary" onclick={openCaesar}>Open CAESAR</button>
      {#if busy}<button class="btn ghost" onclick={stop}>Stop</button>{:else}<button class="btn ghost" onclick={start}>Monitor again</button>{/if}
    {:else if running}
      <button class="btn stop" onclick={stop}>Stop monitoring</button>
    {:else if status === 'signing_in'}
      <button class="btn ghost" onclick={stop}>Cancel</button>
    {:else if status === 'needs_signin'}
      <button class="btn primary" onclick={signIn} disabled={busy}>Solve captcha in Chrome</button>
    {:else}
      <button class="btn primary" onclick={start} disabled={busy}>{signedIn ? 'Start monitoring' : 'Verify and start'}</button>
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
  .msg, .err { display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .msg { margin: var(--space-1) 0 0; color: var(--text-muted); font-size: 12px; text-wrap: pretty; overflow-wrap: anywhere; }
  .count { display: flex; align-items: flex-end; gap: var(--space-3); margin-top: var(--space-1); }
  .count strong { font: 700 40px/0.9 var(--font-sans); letter-spacing: -.035em; font-variant-numeric: tabular-nums; }
  .count strong.none { color: var(--text-muted); font-weight: 400; }
  .count .sub { color: var(--text-muted); font-size: 12px; line-height: 1.3; padding-bottom: 2px; }

  /* Signature move: route strip. The train is the time since the last check. */
  .route { position: relative; height: 18px; margin: var(--space-2) 6px 0; }
  .track { position: absolute; left: 0; right: 0; top: 7px; height: 4px; background: var(--rule); border-radius: 2px; overflow: hidden; }
  .done { height: 100%; background: var(--accent); }
  .stn { position: absolute; top: 3px; width: 12px; height: 12px; border-radius: 50%; background: var(--bg); border: 3px solid var(--accent); }
  .stn.a { left: -6px; } .stn.b { right: -6px; }
  .stn.lit { top: -1px; right: -10px; width: 20px; height: 20px; background: var(--ok); border-color: var(--ok); box-shadow: 0 0 0 4px color-mix(in srgb, var(--ok) 30%, transparent); animation: arrive 520ms var(--ease-out) both; }
  @keyframes arrive { from { transform: scale(.3); opacity: 0; } to { transform: scale(1); opacity: 1; } }
  .status.alert .count strong { color: var(--ok); }
  .status.alert .done { background: var(--ok); }
  .train { position: absolute; top: 4px; width: 10px; height: 10px; margin-left: -5px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 3px var(--bg); transition: left 1s linear; }
  .route-labels { display: flex; justify-content: space-between; margin-top: 2px; font: 500 12px var(--font-mono); font-variant-numeric: tabular-nums; }
  .route-labels em { display: block; font: 500 11px var(--font-sans); font-style: normal; color: var(--text-muted); }
  .route-labels .r { text-align: right; }

  .tabs { display: flex; gap: var(--space-5, 20px); border-bottom: 2px solid var(--rule); flex: none; }
  .tabs button { display: inline-flex; align-items: center; gap: 6px; font: inherit; font-weight: 700; color: var(--text-muted); background: none; border: 0; border-bottom: 3px solid transparent; margin-bottom: -2px; padding: 4px 0 7px; cursor: pointer; transition: color var(--dur) var(--ease-out), border-color var(--dur) var(--ease-out); }
  .tabs button:hover { color: var(--text); }
  .tabs button.active { color: var(--text); border-color: var(--accent); }
  .tabs button:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; border-radius: 2px; }

  .panel { min-height: 0; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-2) var(--space-3); }
  label { display: grid; gap: 3px; min-width: 0; font-size: 11px; font-weight: 600; color: var(--text-muted); }
  input, .grid :global(.combo input), .field :global(.combo input) {
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
  .field { display: grid; gap: 3px; min-width: 0; font-size: 11px; font-weight: 600; color: var(--text-muted); }
  .fhead { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
  .prog { display: grid; gap: 5px; height: var(--field-h); align-content: center; }
  .bar { height: 4px; border-radius: 2px; background: var(--rule); overflow: hidden; }
  .fill { height: 100%; background: var(--accent); border-radius: 2px; transition: width 900ms linear; }
  .plabel { font-size: 11px; font-weight: 500; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .hintline { margin-top: var(--space-2); font-size: 13px; line-height: 1.4; }
  .addlink { justify-self: start; margin: var(--space-1) 0 0; }
  .hint.under { margin: -4px 0 0 78px; }
  .hint.lock { margin: 0; text-align: center; }
  .seg button.on:disabled { opacity: .9; }
  .linkbtn.tiny { margin: 0; font-size: 11px; }
  .linkbtn:disabled { opacity: .5; cursor: progress; }
  .ferr { font-weight: 500; color: var(--bad); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  input::placeholder, .grid :global(.combo input::placeholder) { color: var(--text-muted); font-weight: 400; }
  input:hover:not(:disabled), .grid :global(.combo input:hover:not(:disabled)) { background: color-mix(in srgb, var(--accent) 8%, var(--sunken)); }
  input:focus-visible, .grid :global(.combo input:focus-visible) { outline: none; border-bottom: 2px solid var(--focus); background: var(--bg); box-shadow: 0 0 0 1px var(--rule); }
  input:disabled, .grid :global(.combo input:disabled) { cursor: not-allowed; background: transparent; border-bottom-style: dashed; color: var(--text); }
  .opts { display: grid; gap: var(--space-3); }
  .opt { display: grid; gap: 4px; }
  .opt.inline { grid-template-columns: 70px 1fr auto; align-items: center; gap: var(--space-2); }
  .opt.inline .seg { grid-column: 2 / -1; }
  .opt.inline .range { grid-column: 2; }
  .opt-l { font-size: 12px; font-weight: 600; color: var(--text); }
  .hint { font-size: 11px; color: var(--text-muted); line-height: 1.35; }
  .stepper { display: flex; align-items: stretch; gap: 4px; }
  .stepper input { width: 64px; text-align: center; font-weight: 700; font-size: 15px; -moz-appearance: textfield; appearance: textfield; }
  .stepper input::-webkit-outer-spin-button, .stepper input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
  .stepper button, .seg button { font: inherit; font-weight: 700; color: var(--text); background: var(--sunken); border: 0; border-radius: var(--radius); cursor: pointer; transition: background-color var(--dur) var(--ease-out), color var(--dur) var(--ease-out); }
  .stepper button { width: 32px; font-size: 16px; }
  .seg { display: flex; gap: 4px; }
  .seg button { flex: 1; height: var(--field-h); font-size: 12px; white-space: nowrap; padding: 0 4px; }
  .seg button.on { background: var(--accent); color: var(--on-accent); }
  .stepper button:hover:not(:disabled), .seg button:hover:not(:disabled):not(.on) { background: color-mix(in srgb, var(--accent) 14%, var(--sunken)); }
  .stepper button:focus-visible, .seg button:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
  .stepper button:disabled, .seg button:disabled { opacity: .45; cursor: not-allowed; }
  .spark { margin-left: auto; flex: none; align-self: center; }
  .chips { display: flex; gap: 4px; margin-bottom: 6px; }
  .chip { display: inline-flex; align-items: center; justify-content: center; gap: 5px; min-width: 0; flex: 1 1 0; height: 22px; padding: 0 8px; font: inherit; font-size: 12px; font-weight: 700; color: var(--text-muted); background: var(--sunken); border: 0; border-radius: 999px; cursor: pointer; transition: background-color var(--dur) var(--ease-out), color var(--dur) var(--ease-out); }
  .chip .ct { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chip:hover:not(.on) { background: color-mix(in srgb, var(--accent) 14%, var(--sunken)); color: var(--text); }
  .chip.on { background: var(--accent); color: var(--on-accent); }
  .chip.add { flex: none; width: 22px; padding: 0; font-size: 15px; }
  .chip:focus-visible { outline: 2px solid var(--focus); outline-offset: 1px; }
  .cdot { width: 7px; height: 7px; border-radius: 50%; background: var(--ok); flex: none; box-shadow: 0 0 0 1.5px var(--bg); }
  .okmsg { margin: 0; color: var(--ok); font-weight: 600; font-size: 12px; }
  .opts .linkbtn.auto { margin: 0; font-size: 12px; }
  .of { font-size: 12px; color: var(--text-muted); font-variant-numeric: tabular-nums; }
  .range { accent-color: var(--accent); height: var(--field-h); width: 100%; background: none; border: 0; padding: 0; cursor: pointer; }
  .range:disabled { cursor: not-allowed; opacity: .45; }
  .check { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600; color: var(--text); }
  .check input { width: 16px; height: 16px; padding: 0; accent-color: var(--accent); cursor: pointer; }
  .when { display: flex; align-items: center; gap: var(--space-2); font-size: 12px; color: var(--text-muted); }
  .when input { width: 118px; padding: 0 6px; }
  .opts .linkbtn { justify-self: start; margin: 0; }
  .tabend { margin: 0 0 6px auto !important; }
  .linkbtn { margin-top: var(--space-2); font: inherit; font-size: 12px; font-weight: 600; color: var(--accent); background: none; border: 0; padding: 2px 0; cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
  .linkbtn:hover { color: var(--accent-hover); }
  .linkbtn:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; border-radius: 2px; }
  .note { margin: var(--space-2) 0 0; font-size: 12px; color: var(--text-muted); }
  .err { margin: 0; color: var(--bad); font-weight: 600; font-size: 12px; }

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
    .stn.lit { animation: none; }
    .train, .btn, input, select, .tabs button, .bandbtn, .fill { transition: none; }
  }
</style>
