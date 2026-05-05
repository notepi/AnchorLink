'use client';

// This uses vanilla JS to test if any JS runs at all
export default function JsVanilla() {
  // Use ref to access DOM directly
  const divRef = { current: null };

  if (typeof window !== 'undefined') {
    setTimeout(() => {
      const el = document.getElementById('vanilla-result');
      if (el) {
        el.textContent = 'Vanilla JS UPDATED!';
        el.style.background = 'yellow';
      }
    }, 1000);
  }

  return (
    <div>
      <p id="vanilla-result">Vanilla JS: not updated</p>
    </div>
  );
}