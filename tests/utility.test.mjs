import assert from 'node:assert/strict';
import {calculate,convert,textStats,utilityAnswer} from '../docs/utility.mjs';
for(const [q,v] of [["2+3*4","14"],["(2+3)*4","20"],["What is 17 plus 26?","43"],["15% of 250","37.5"],["-2 * (3+4)","-14"],["0.1+0.2","0.3"],["1,000+25","1025"],["10 divided by 4","2.5"]])assert.equal(calculate(q).text,v);
assert.equal(calculate('what is gravity?'),null);assert.equal(calculate('2+alert(1)'),null);assert.ok(calculate('2/0').error);assert.ok(calculate('2*(3').error);
for(const [q,v] of [["5 km to m","5000 m"],["32 f to c","0 °C"],["100 c to f","212 °F"],["2.54 cm to in","1 in"],["1 lb to g","453.59237 g"],["1 us gal to l","3.785411784 L"]])assert.equal(convert(q).text,v);
assert.ok(convert('1 kg to km').error);assert.ok(convert('-1 k to c').error);assert.equal(textStats('One two\nthree').words,3);assert.equal(utilityAnswer('17 plus 26').kind,'Calculator');console.log('Utility checks passed');
