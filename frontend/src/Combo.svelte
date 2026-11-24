<script>
  // Searchable replacement for a long <select>. items: [{ value, label, group? }].
  let { items = [], value = '', placeholder = 'Search…', name = '', disabled = false, onpick, extra = null, up = false } = $props()
  let open = $state(false)
  let q = $state('')
  let hi = $state(0)
  let box
  let input

  let shown = $derived(items.find((i) => i.value === value)?.label ?? '')
  let words = $derived(q.trim().toLowerCase().replace(/_/g, ' ').split(/\s+/).filter(Boolean))
  let list = $derived(words.length ? items.filter((i) => words.every((w) => i.label.toLowerCase().replace(/_/g, ' ').includes(w))) : items)

  function show() { if (disabled) return; q = ''; hi = Math.max(0, list.findIndex((i) => i.value === value)); open = true }
  function pick(i) { open = false; q = ''; onpick?.(i.value); input?.blur() }
  function onkey(e) {
    if (!open && (e.key === 'ArrowDown' || e.key === 'Enter')) { show(); e.preventDefault(); return }
    if (!open) return
    const n = list.length + (extra ? 1 : 0)
    if (e.key === 'ArrowDown') { hi = Math.min(n - 1, hi + 1); e.preventDefault() }
    else if (e.key === 'ArrowUp') { hi = Math.max(0, hi - 1); e.preventDefault() }
    else if (e.key === 'Enter') { e.preventDefault(); if (hi < list.length) pick(list[hi]); else if (extra) pick({ value: extra.value }) }
    else if (e.key === 'Escape') { open = false; e.stopPropagation() }
    else if (e.key === 'Tab') open = false
    queueMicrotask(() => box?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' }))
  }
  function onblur() { setTimeout(() => (open = false), 120) }
</script>

<div class="combo" bind:this={box}>
  <input bind:this={input} {name} role="combobox" aria-expanded={open} aria-autocomplete="list" autocomplete="off" spellcheck="false" {disabled}
    placeholder={open ? 'Type to search' : placeholder}
    value={open ? q : shown}
    oninput={(e) => { q = e.currentTarget.value; hi = 0; open = true }}
    onfocus={show} onclick={() => { if (!open) show() }} onkeydown={onkey} onblur={onblur} />
  <span class="caret" aria-hidden="true"></span>
  {#if open}
    <ul role="listbox" class:up>
      {#each list as it, i}
        {#if it.group && it.group !== list[i - 1]?.group}<li class="grp" role="presentation">{it.group}</li>{/if}
        <li role="option" aria-selected={i === hi} class:on={it.value === value} onmousedown={(e) => { e.preventDefault(); pick(it) }} onmouseenter={() => (hi = i)}>{it.label}</li>
      {/each}
      {#if !list.length}<li class="none" role="presentation">No match</li>{/if}
      {#if extra}<li role="option" aria-selected={hi === list.length} class="extra" onmousedown={(e) => { e.preventDefault(); pick({ value: extra.value }) }} onmouseenter={() => (hi = list.length)}>{extra.label}</li>{/if}
    </ul>
  {/if}
</div>

<style>
  .combo { position: relative; }
  input { width: 100%; padding-right: 22px; text-overflow: ellipsis; }
  .caret { position: absolute; right: 8px; top: 50%; width: 6px; height: 6px; margin-top: -5px; border: solid var(--text-muted); border-width: 0 1.5px 1.5px 0; transform: rotate(45deg); pointer-events: none; }
  ul { position: absolute; z-index: 20; right: 0; width: max(100%, 250px); top: calc(100% + 3px); max-height: 136px; overflow-y: auto; margin: 0; padding: 3px; list-style: none; background: var(--bg); border: 1px solid var(--rule); border-radius: 6px; box-shadow: 0 6px 18px rgb(0 0 0 / .22); }
  ul.up { top: auto; bottom: calc(100% + 3px); }
  li { padding: 5px 8px; border-radius: 4px; font-size: 12px; line-height: 1.25; color: var(--text); cursor: pointer; text-transform: none; font-weight: 500; letter-spacing: 0; }
  li.grp { position: sticky; top: -3px; background: var(--bg); padding: 6px 8px 3px; font-size: 10px; font-weight: 700; color: var(--text-muted); cursor: default; text-transform: uppercase; letter-spacing: .04em; }
  li.none { color: var(--text-muted); cursor: default; }
  li[aria-selected='true'] { background: var(--accent); color: var(--on-accent); }
  li.on:not([aria-selected='true']) { font-weight: 700; }
  li.extra { color: var(--text-muted); border-top: 1px solid var(--rule); border-radius: 0 0 4px 4px; margin-top: 2px; }
  li.extra[aria-selected='true'] { color: var(--on-accent); }
</style>
