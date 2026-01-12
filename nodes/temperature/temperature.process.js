export default async ({inputs, settings, config}) => {

  
  // Use input value if provided, otherwise use the setting value
  let value = (inputs.value !== undefined && inputs.value !== null) ? Number(inputs.value) : Number(settings.value);
  
  // Hard-code min to 0, max based on allow_experimental setting
  const min = 0;
  const max = settings.allow_experimental ? 2 : 1;
  
  // Clamp value to valid range
  value = Math.max(min, Math.min(max, value));

  return { value };
};

