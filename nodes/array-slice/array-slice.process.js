export default async ({inputs, settings, config, nodeConfig}) => {

  const array = Array.isArray(inputs.array) ? inputs.array : [inputs.array];

  let start = inputs.start !== undefined ? parseInt(inputs.start) : 0;
  if (isNaN(start)) {
    throw new Error("array-slice: 'start' must be a valid number");
  }

  let end = inputs.end !== undefined ? parseInt(inputs.end) : undefined;
  if (end !== undefined && isNaN(end)) {
    throw new Error("array-slice: 'end' must be a valid number");
  }

  return {
    array: array.slice(start, end)
  };
}; 