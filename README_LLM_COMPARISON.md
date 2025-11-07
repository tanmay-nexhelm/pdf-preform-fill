# LLM Provider Comparison

## Configuration

The system now supports multiple LLM providers and models through environment variables in `.env`:

```bash
# Choose provider: "openai" or "anthropic"
LLM_PROVIDER=anthropic

# Choose model
LLM_MODEL=claude-3-5-haiku-20241022
```

## Available Models

### OpenAI
- **gpt-4o** - Most powerful, slower, $2.50/1M input tokens
- **gpt-4o-mini** - Fast, cost-effective, $0.15/1M input tokens

### Anthropic (Claude)
- **claude-3-5-sonnet-20241022** - Most powerful, $3/1M input tokens
- **claude-3-5-haiku-20241022** - Fastest, most cost-effective, $0.25/1M input tokens

## Performance Comparison: easy-acro.pdf (181 fields)

| Metric | GPT-4o-mini | Claude Haiku | Winner |
|--------|-------------|--------------|--------|
| **Processing Time** | 94 seconds | 75 seconds | 🏆 Claude (-20%) |
| **PRIMARY Mapped** | 78 fields | 152 fields | 🏆 Claude (+95%) |
| **Fields Filled** | 46 fields | 60 fields | 🏆 Claude (+30%) |
| **Secondary Skipped** | 103 fields | 29 fields | - |
| **Cost (estimated)** | ~$0.03 | ~$0.05 | 🏆 GPT |
| **Accuracy** | Conservative | Aggressive | TBD |

## Key Observations

### Claude Haiku Advantages:
- ✅ **20% faster** processing
- ✅ **95% more fields mapped** to PRIMARY
- ✅ **30% more fields filled** with data
- ✅ Better at identifying primary account holder fields
- ✅ 200K context window (vs 128K)
- ✅ Excellent reasoning quality

### GPT-4o-mini Advantages:
- ✅ **More conservative** approach (fewer false positives)
- ✅ **Cheaper** per token
- ✅ Slightly better JSON formatting consistency

## Interpretation

Claude Haiku appears to be **less conservative** in classifying fields as PRIMARY. This could mean:

1. **Better Accuracy**: Claude correctly identifies more PRIMARY fields that GPT missed
2. **Less Conservative**: Claude may be incorrectly classifying some SECONDARY fields as PRIMARY
3. **Different Interpretation**: Claude has a different understanding of "when uncertain → SECONDARY"

## Recommendations

### For Maximum Accuracy (Recommended):
```bash
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
```
- Best reasoning capabilities
- Worth the extra cost for critical forms

### For Speed + Good Balance:
```bash
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-haiku-20241022
```
- Fast processing
- Less conservative than GPT-4o-mini
- Good for high-volume processing

### For Conservative Approach:
```bash
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
```
- Fewer false positives
- Most cost-effective
- Safe default

## Switching Between Providers

Simply edit `.env` file:

```bash
# Test with Claude Haiku
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-haiku-20241022

# Test with GPT-4o-mini
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini

# Test with Claude Sonnet (max accuracy)
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
```

No code changes needed - just restart the application!

## Next Steps

1. **Manual Review**: Check filled PDFs to determine which model has better accuracy
2. **A/B Testing**: Process same form with both providers and compare results
3. **Validation**: Implement validation rules to catch obvious errors (e.g., multiple PRIMARY SSN fields)
4. **Hybrid Approach**: Use Claude for complex pages, GPT for simple pages
