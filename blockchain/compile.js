const solc = require('solc');
const fs = require('fs');

const source = fs.readFileSync('DIDRegistry.sol', 'utf8');

// Try multiple EVM targets since Ganache installations vary in which
// hardfork they emulate. The ABI/function selectors are identical across
// all of these (they depend only on the function signatures, not the
// compiled opcodes), so whichever variant actually deploys is safe to use.
const evmVersions = ['istanbul', 'berlin', 'london', 'paris', 'shanghai', 'cancun'];

let abiWritten = false;
for (const evmVersion of evmVersions) {
  const input = {
    language: 'Solidity',
    sources: { 'DIDRegistry.sol': { content: source } },
    settings: {
      evmVersion,
      outputSelection: { '*': { '*': ['abi', 'evm.bytecode.object', 'evm.methodIdentifiers'] } }
    }
  };

  const output = JSON.parse(solc.compile(JSON.stringify(input)));
  if (output.errors && output.errors.some(e => e.severity === 'error')) {
    console.error(`[${evmVersion}] compile error:`, output.errors.map(e => e.formattedMessage).join('\n'));
    continue;
  }
  const contract = output.contracts['DIDRegistry.sol']['DIDRegistry'];
  fs.writeFileSync(`bytecode_${evmVersion}.txt`, contract.evm.bytecode.object);
  console.log(`[${evmVersion}] bytecode written (${contract.evm.bytecode.object.length / 2} bytes)`);

  if (!abiWritten) {
    fs.writeFileSync('abi.json', JSON.stringify(contract.abi, null, 2));
    fs.writeFileSync('selectors.json', JSON.stringify(contract.evm.methodIdentifiers, null, 2));
    console.log('Method selectors (identical across all EVM targets):');
    console.log(contract.evm.methodIdentifiers);
    abiWritten = true;
  }
}