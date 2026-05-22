Random fun and utility cogs for [Red-DiscordBot](https://github.com/cog-creators/red-discordbot).

### WritingPrompt 
![Static Badge](https://img.shields.io/badge/Cog_Status:-Ready_To_Use-brightgreen?style=flat)

Automatically pulls the top daily post from [r/WritingPrompts](https://www.reddit.com/r/WritingPrompts/) and posts it in a channel of your choosing. 
It also has the ability to add custom prompts in through the command `/writingprompt add`

You can take it further and react to your own prompt response with ❓ and your response will be given feedback by an LLM. This does require an [OpenRouter](https://openrouter.ai/) API key that you would put in using `/writingprompt apikey <api>`. I do intend to update this to be a variable in the future so the user can select thier own model, but at the moment it's currently hardcoded to be [openai/gpt-oss-120b:free](https://openrouter.ai/openai/gpt-oss-120b:free), so the response will be slower but they are free. 


### VoteBan
![Static Badge](https://img.shields.io/badge/Cog_Status:-Ready_To_Use-brightgreen?style=flat)

Allow users to democratically vote to ban a user from your Discord server. A user can start a ban vote, and a reason and then it will be live for 24 hours: 
- If at least 50% of votes to ban someone, they are removed from the server. 
- If less than 50% votes to ban, the user in question is then immune to being voted out for the next 6 months. 
- If a vote does not include 1/3 of users, the vote fails and nobody is banned nor are any cooldowns applied.  
The user who cast a vote has a 6 month cooldown from being able to start another vote, the user who started the vote is the only user who is not annonomous. 

### FAQ
![Static Badge](https://img.shields.io/badge/Cog_Status:-Under_Development-orange?style=flat)
This is a FAQ cog that is written to be data based, so that all you have to do is add in your own custom faq embeds and everything else will work just fine. At the moment, it's setup to be used on my own personal server, but if you want to use it for yourself, just fork the repository and modify the `self.faq_data` section. 


---
### Licence
These cogs were developed with assistance from [GLM-4.7](https://z.ai/blog/glm-4.7). The code is released under the MIT License.

