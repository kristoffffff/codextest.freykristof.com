function calculate(a: number, b: number, op: string): number {
  switch (op) {
    case '+':
      return a + b;
    case '-':
      return a - b;
    case '*':
      return a * b;
    case '/':
      return b !== 0 ? a / b : NaN;
    default:
      return NaN;
  }
}

const num1 = document.getElementById('num1') as HTMLInputElement;
const num2 = document.getElementById('num2') as HTMLInputElement;
const operation = document.getElementById('operation') as HTMLSelectElement;
const calculateBtn = document.getElementById('calculate');
const resultSpan = document.getElementById('result');

calculateBtn?.addEventListener('click', () => {
  const a = parseFloat(num1.value);
  const b = parseFloat(num2.value);
  const op = operation.value;
  const result = calculate(a, b, op);
  if (resultSpan) {
    resultSpan.textContent = isNaN(result) ? 'Hiba' : result.toString();
  }
});

export {};
