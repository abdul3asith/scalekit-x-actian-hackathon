type Message = {
    role: "system" | "user" | "assistant";
    content: string;
  };
  
  export async function askNebius(messages: Message[]) {
    const baseUrl = process.env.NEBIUS_BASE_URL;
    const apiKey = process.env.NEBIUS_API_KEY;
    const model = process.env.NEBIUS_MODEL;
  
    if (!baseUrl || !apiKey || !model) {
      throw new Error("Missing Nebius env vars");
    }
  
    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/chat/completions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        messages,
        temperature: 0.2,
      }),
    });
  
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Nebius error: ${errorText}`);
    }
  
    const data = await response.json();
  
    return data.choices?.[0]?.message?.content || "";
  }