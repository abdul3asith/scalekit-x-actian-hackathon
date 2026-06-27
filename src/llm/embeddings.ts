export async function embedText(text: string): Promise<number[]> {
    const baseUrl = process.env.NEBIUS_BASE_URL;
    const apiKey = process.env.NEBIUS_API_KEY;
    const model = process.env.NEBIUS_EMBED_MODEL;
  
    if (!baseUrl || !apiKey || !model) {
      throw new Error("Missing Nebius embedding env vars");
    }
  
    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/embeddings`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        input: text,
      }),
    });
  
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Nebius embedding error: ${errorText}`);
    }
  
    const data = await response.json();
    return data.data?.[0]?.embedding;
  }