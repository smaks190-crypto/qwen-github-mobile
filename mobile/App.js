import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Alert, AppState, FlatList, KeyboardAvoidingView,
  Modal, Platform, SafeAreaView, ScrollView, StyleSheet, Text, TextInput,
  TouchableOpacity, View } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import TermuxBridge from './modules/termux-bridge';
import CreatePRModal from './src/components/CreatePRModal';
import { PROVIDERS, assertSettings, isEditRequest, newJobId, parseAgentResponse } from './src/utils/agentRequest';

const C = { bg:'#0d0d14', panel:'#1b192b', border:'#342e4b', ink:'#f6f2ff', muted:'#aaa4c1', accent:'#9866ff', green:'#56d6a1', red:'#ff7e97' };
const DEFAULTS = { repo:'smaks190-crypto/qwen-github-mobile', provider:'qwencloud',
  baseUrl:PROVIDERS.qwencloud.baseUrl, model:PROVIDERS.qwencloud.model, githubToken:'', aiKey:'' };
const STORAGE = 'qwen_github_local_settings_v2';

function Action({label,onPress,disabled,subtle}) {
  return <TouchableOpacity accessibilityRole="button" onPress={onPress} disabled={disabled}
    style={[styles.action,subtle&&styles.subtle,disabled&&{opacity:.45}]}>
    <Text style={styles.actionText}>{label}</Text>
  </TouchableOpacity>;
}

function SettingField({label,value,onChangeText,secret,placeholder,multiline}) {
  return <View style={{gap:8}}>
    <Text style={styles.label}>{label}</Text>
    <TextInput style={[styles.field,multiline&&{height:85}]} value={value} onChangeText={onChangeText}
      autoCapitalize="none" autoCorrect={false} secureTextEntry={!!secret}
      placeholder={placeholder} placeholderTextColor={C.muted} multiline={multiline}/>
  </View>;
}

export default function App() {
  const [settings,setSettings] = useState(DEFAULTS);
  const [draft,setDraft] = useState(DEFAULTS);
  const [settingsOpen,setSettingsOpen] = useState(false);
  const [ready,setReady] = useState(false);
  const [input,setInput] = useState('');
  const [busy,setBusy] = useState(false);
  const [messages,setMessages] = useState([{id:'welcome',role:'assistant',text:'Привет! Я Qwen GitHub Agent. Напиши задачу: прочитать код, проверить PR или исправить ошибку. Работаю через Termux на твоём телефоне, без Render.'}]);
  const [prepared,setPrepared] = useState(null);
  const [prOpen,setPrOpen] = useState(false);
  const activeJob = useRef(null);
  const mounted = useRef(true);
  const list = useRef(null);

  useEffect(() => {
    mounted.current = true;
    (async () => {
      try {
        const saved = await SecureStore.getItemAsync(STORAGE);
        if (saved) {
          const updated = {...DEFAULTS,...JSON.parse(saved)};
          setSettings(updated); setDraft(updated);
          setSettingsOpen(!updated.githubToken || !updated.aiKey);
        } else setSettingsOpen(true);
      } catch (_) {setSettingsOpen(true);}
      finally {setReady(true);}
    })();
    return () => {mounted.current = false;};
  }, []);

  useEffect(() => {
    const listener = AppState.addEventListener('change', state => {
      if (state !== 'active' && activeJob.current) {
        // Best-effort cancellation; force-killing an app may bypass lifecycle notifications.
        TermuxBridge.cancel(activeJob.current).catch(() => {});
      }
    });
    return () => listener.remove();
  }, []);

  const assistant = useCallback((text,extra={}) => {
    if (!mounted.current) return;
    setMessages(items => [...items, {id:`a-${Date.now()}-${Math.random()}`,role:'assistant',text,...extra}]);
  }, []);

  const save = async () => {
    try {
      assertSettings(draft);
      await SecureStore.setItemAsync(STORAGE, JSON.stringify(draft), {
        keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
      });
      setSettings(draft); setSettingsOpen(false);
    } catch(error) { Alert.alert('Проверь настройки',String(error.message||error)); }
  };

  const requestAgent = async payload => {
    const text = await TermuxBridge.run(JSON.stringify(payload));
    return parseAgentResponse(text);
  };

  const runTask = async (prompt,mode) => {
    const jobId = newJobId();
    activeJob.current = jobId;
    setBusy(true);
    try {
      const result = await requestAgent({action:'task',mode,job_id:jobId,prompt,
        repo:settings.repo,github_token:settings.githubToken,ai_key:settings.aiKey,
        provider:settings.provider,base_url:settings.baseUrl,model:settings.model});
      assistant(result.message || 'Готово.',result.prepared ? {
        prepared:{jobId,repo:settings.repo,branch:result.branch,base:result.base,files:result.files},
      }:{});
    } catch(e) {assistant('Не удалось выполнить задачу: '+String(e.message||e));}
    finally {activeJob.current=null; if(mounted.current)setBusy(false);}
  };

  const send = async () => {
    const prompt=input.trim();
    if(!prompt||busy) return;
    try {assertSettings(settings);} catch(error){setDraft(settings);setSettingsOpen(true);Alert.alert('Нужны два ключа',error.message);return;}
    if (!TermuxBridge.isTermuxInstalled()) {
      Alert.alert('Нужен Termux','Установи Termux (F-Droid/GitHub) и выполни первоначальную настройку из README.'); return;
    }
    setInput('');
    setMessages(items=>[...items,{id:`u-${Date.now()}`,role:'user',text:prompt}]);
    if(isEditRequest(prompt)) {
      Alert.alert('Изменить код?', 'Qwen подготовит изменения в отдельной локальной ветке. Отправить её в GitHub можно будет только после твоего подтверждения.',[
        {text:'Отмена',style:'cancel',onPress:()=>assistant('Редактирование отменено.')},
        {text:'Разрешить',onPress:()=>runTask(prompt,'edit')},
      ]);
    } else await runTask(prompt,'chat');
  };

  const pushPrepared = info => {
    Alert.alert('Отправить ветку в GitHub?',`${info.repo}\n${info.branch}\n\nPR не будет создан без твоего отдельного подтверждения.`,[
      {text:'Отмена',style:'cancel'},
      {text:'Отправить',onPress:async()=>{
        activeJob.current=info.jobId;setBusy(true);
        try {
          const result=await requestAgent({action:'push',job_id:info.jobId,repo:info.repo,
            github_token:settings.githubToken});
          const next={repo:info.repo,head:result.branch,base:result.base,title:result.title,body:result.description};
          setPrepared(next);setPrOpen(true);
          assistant(result.message);
        }catch(e){assistant('Не удалось отправить ветку: '+String(e.message||e));}
        finally{activeJob.current=null;if(mounted.current)setBusy(false);}
      }}
    ]);
  };

  const renderMessage = ({item}) => <View style={[styles.bubble,item.role==='user'?styles.user:styles.bot]}>
    <Text selectable style={styles.message}>{item.text}</Text>
    {item.prepared&&<View style={styles.preview}>
      <Text style={styles.secondary}>Подготовлено файлов: {item.prepared.files?.length||0}</Text>
      <Text style={styles.secondary}>Ветка: {item.prepared.branch}</Text>
      <Action label="Отправить ветку и создать PR" disabled={busy} onPress={()=>pushPrepared(item.prepared)}/>
    </View>}
  </View>;

  if(!ready)return <SafeAreaView style={styles.safe}><ActivityIndicator style={{marginTop:100}} color={C.accent}/></SafeAreaView>;
  return <SafeAreaView style={styles.safe}>
    <View style={styles.header}>
      <View style={{flex:1}}><Text style={styles.title}>Qwen <Text style={{color:C.accent}}>GitHub</Text></Text>
        <Text style={styles.secondary}>Локально через Termux · {settings.repo}</Text></View>
      <Action label="⚙" subtle onPress={()=>{setDraft(settings);setSettingsOpen(true);}}/>
    </View>
    <FlatList ref={list} data={messages} keyExtractor={m=>m.id} renderItem={renderMessage}
      onContentSizeChange={()=>list.current?.scrollToEnd({animated:true})}
      contentContainerStyle={styles.messages} keyboardShouldPersistTaps="handled" />
    {busy&&<View style={styles.progress}><ActivityIndicator color={C.accent}/><Text style={styles.secondary}>Qwen работает в Termux. Результат появится здесь.</Text></View>}
    <KeyboardAvoidingView behavior={Platform.OS==='ios'?'padding':undefined}>
      <View style={styles.composer}>
        <TextInput style={styles.composeInput} placeholder="Напиши задачу..." placeholderTextColor={C.muted}
          value={input} onChangeText={setInput} multiline editable={!busy} maxLength={5000}/>
        <Action label="➤" onPress={send} disabled={busy||!input.trim()}/>
      </View>
    </KeyboardAvoidingView>
    <CreatePRModal visible={prOpen} prepared={prepared} selectedRepo={settings.repo} onClose={()=>setPrOpen(false)}/>
    <Modal animationType="slide" visible={settingsOpen} onRequestClose={()=>setSettingsOpen(false)}>
      <SafeAreaView style={styles.safe}>
        <View style={styles.settingsTitle}><Text style={styles.title}>Настройки</Text>
          <Action label="✕" subtle onPress={()=>setSettingsOpen(false)}/></View>
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.settings}>
          <Text style={styles.secondary}>Render и сервер больше не нужны. Сохрани оба ключа на телефоне. Termux запускается в фоне только на время задачи.</Text>
          <SettingField label="РЕПОЗИТОРИЙ GITHUB" value={draft.repo} onChangeText={repo=>setDraft(v=>({...v,repo}))} placeholder="owner/repo"/>
          <SettingField label="GITHUB PERSONAL ACCESS TOKEN" secret value={draft.githubToken}
            onChangeText={githubToken=>setDraft(v=>({...v,githubToken}))} placeholder="github_pat_..."/>
          <Text style={styles.label}>AI-ПРОВАЙДЕР</Text>
          <View style={styles.providerRow}>{Object.entries(PROVIDERS).map(([id,p])=><TouchableOpacity key={id}
            onPress={()=>setDraft(v=>({...v,provider:id,baseUrl:p.baseUrl,model:p.model}))}
            style={[styles.provider,draft.provider===id&&styles.providerActive]}>
            <Text style={styles.message}>{p.name}</Text>
          </TouchableOpacity>)}</View>
          <SettingField label="AI API KEY" secret value={draft.aiKey}
            onChangeText={aiKey=>setDraft(v=>({...v,aiKey}))} placeholder="Ключ выбранного AI-провайдера"/>
          <SettingField label="AI API URL (HTTPS)" value={draft.baseUrl}
            onChangeText={baseUrl=>setDraft(v=>({...v,baseUrl}))} placeholder="https://.../v1"/>
          <SettingField label="МОДЕЛЬ" value={draft.model}
            onChangeText={model=>setDraft(v=>({...v,model}))} placeholder="Название модели"/>
          <View style={styles.notice}><Text style={styles.secondary}>Бесплатные модели могут иметь лимиты и меняться. Проверь условия выбранного провайдера. Ключи сохраняются через Android SecureStore и передаются только локальному Termux при выполнении задания.</Text></View>
          <View style={styles.notice}><Text style={styles.secondary}>Перед первым использованием: установи Termux, Python, Git и Qwen Code, выполни setup.sh из репозитория. Разреши приложению запускать команды Termux через Android Settings → Apps → Qwen GitHub Agent → Permissions → Additional permissions.</Text></View>
          <Action label="Сохранить ключи и вернуться в чат" onPress={save}/>
        </ScrollView>
      </SafeAreaView>
    </Modal>
  </SafeAreaView>;
}

const styles=StyleSheet.create({
  safe:{flex:1,backgroundColor:C.bg},
  header:{flexDirection:'row',alignItems:'center',gap:10,padding:16,borderBottomWidth:1,borderColor:C.border},
  title:{color:C.ink,fontSize:24,fontWeight:'800'},
  secondary:{fontSize:12,color:C.muted,lineHeight:19},
  messages:{padding:14,paddingBottom:25},
  bubble:{maxWidth:'94%',borderRadius:16,padding:14,marginVertical:6},
  user:{backgroundColor:'#42316c',alignSelf:'flex-end'},
  bot:{backgroundColor:C.panel,alignSelf:'flex-start',borderWidth:1,borderColor:C.border},
  message:{color:C.ink,fontSize:14,lineHeight:21},
  preview:{borderTopWidth:1,borderColor:C.border,marginTop:12,paddingTop:10,gap:7},
  action:{backgroundColor:C.accent,alignItems:'center',justifyContent:'center',paddingHorizontal:13,paddingVertical:12,borderRadius:13},
  subtle:{backgroundColor:C.panel,borderWidth:1,borderColor:C.border},
  actionText:{color:'white',fontWeight:'700',fontSize:13},
  composer:{flexDirection:'row',alignItems:'flex-end',gap:8,padding:10,borderTopWidth:1,borderColor:C.border},
  composeInput:{flex:1,maxHeight:150,minHeight:49,padding:13,color:C.ink,backgroundColor:C.panel,borderRadius:13,borderWidth:1,borderColor:C.border},
  progress:{flexDirection:'row',alignItems:'center',gap:10,padding:10},
  settingsTitle:{padding:18,flexDirection:'row',alignItems:'center',justifyContent:'space-between'},
  settings:{padding:20,paddingBottom:40,gap:18},
  label:{color:C.accent,fontSize:12,fontWeight:'800'},
  field:{backgroundColor:C.panel,borderRadius:12,padding:13,minHeight:49,color:C.ink,borderWidth:1,borderColor:C.border},
  providerRow:{flexDirection:'row',flexWrap:'wrap',gap:8},
  provider:{padding:10,borderWidth:1,borderColor:C.border,borderRadius:12,backgroundColor:C.panel},
  providerActive:{borderColor:C.accent,backgroundColor:'#44316d'},
  notice:{padding:14,backgroundColor:C.panel,borderRadius:12,borderWidth:1,borderColor:C.border},
});
