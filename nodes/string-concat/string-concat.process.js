export default async ({inputs, settings, config, nodeConfig}) => {

  const a = inputs.string_a != null ? String(inputs.string_a) : '';
  const b = inputs.string_b != null ? String(inputs.string_b) : '';

  return {
    text: `${a}${b}`
  };
}; 