export default async ({ inputs, settings, config }) => {
  const stripe = config.integrations?.stripe;
  if (!stripe) {
    throw new Error("Stripe integration not configured. Add your Stripe secret key to config.keys.stripe");
  }

  const result = await stripe.listCustomers({
    email: inputs.email || undefined,
    limit: inputs.limit ?? 10,
    starting_after: inputs.starting_after || undefined,
  });

  return {
    customers: result.data || [],
    has_more: result.has_more || false,
    count: result.data ? result.data.length : 0,
  };
};
