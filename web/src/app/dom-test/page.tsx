'use client';

export default function ClickTest() {
  return (
    <div>
      <p>Click the button:</p>
      <button onClick={() => {
        const el = document.getElementById('result');
        if (el) el.textContent = 'Button clicked!';
      }}>
        Click me
      </button>
      <p id="result">Not clicked</p>
    </div>
  );
}