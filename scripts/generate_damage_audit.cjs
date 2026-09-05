// Regenerate pinned expectations with an independently installed oracle:
// node scripts/generate_damage_audit.cjs /path/to/node_modules/@smogon/calc
const fs = require('node:fs');
const path = require('node:path');
const oraclePath = process.argv[2] || '@smogon/calc';
const {Pokemon, Move, Field, calculate, Generations} = require(oraclePath);
const filename = path.join(__dirname, '../tests/calc/damage_audit_cases.json');
const fixture = JSON.parse(fs.readFileSync(filename, 'utf8'));
const gen = Generations.get(9);
for (const test of fixture.cases) {
  const m = test.mods;
  const common = {
    level: test.level, nature: 'Serious', boostedStat: 'auto',
    overrides: {baseStats: test.base, types: test.types || ['Normal']},
  };
  const attacker = new Pokemon(gen, 'Mew', {
    ...common, ability: m.attacker_ability || 'Pressure', item: m.attacker_item,
    boosts: {
      atk: (m.attack_stage || 0) + (m.commander_active ? 2 : 0),
      spa: (m.special_attack_stage || 0) + (m.commander_active ? 2 : 0),
    },
  });
  const defender = new Pokemon(gen, 'Mew', {
    ...common, ability: m.defender_ability || 'Pressure', item: m.defender_item,
    boosts: {
      def: (m.defense_stage || 0) + (m.defender_commander_active ? 2 : 0),
      spd: (m.special_defense_stage || 0) + (m.defender_commander_active ? 2 : 0),
    },
  });
  const move = new Move(gen, test.move.name, {isCrit: m.is_critical});
  const field = new Field({
    gameType: 'Doubles', isSwordOfRuin: m.sword_of_ruin, isBeadsOfRuin: m.beads_of_ruin,
  });
  const result = calculate(gen, attacker, defender, move, field);
  test.rolls = typeof result.damage === 'number' ? Array(16).fill(result.damage) : result.damage;
}
fixture.oracle = '@smogon/calc ' + require(path.join(oraclePath, 'package.json')).version;
fs.writeFileSync(filename, JSON.stringify(fixture, null, 2) + '\n');
console.log(`Generated ${fixture.cases.length} oracle cases using ${fixture.oracle}`);
