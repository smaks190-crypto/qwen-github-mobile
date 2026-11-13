import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, ActivityIndicator, FlatList, SafeAreaView, ScrollView,
  StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import * as Notifications from 'expo-notifications';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true, shouldShowList: true, shouldPlaySound: false, shouldSetBadge: false,
  }),
});

const COLORS = { bg: '#0d0d14', panel: '#1a1928', border: '#313047', ink: '#f5f1ff',
  muted: '#a8a4bf', purple: '#9569ff', green: '#61d6a1', danger: '#ff7b90' };

function Btn({ label, onPress, disabled, secondary, danger }) {
  return <TouchableOpacity disabled={disabled} onPress={onPress}
    style={[s.btn, secondary && s.secondary, danger && s.danger, disabled && s.disabled]}>
    <Text style={s.btnText}>{label}</Text>
  </TouchableOpacity>;
}

export default function App() {
  const [url, setUrl] = useState('');
  const [token, setToken] = useState('');
  const [settings, setSettings] = useState(true);
  const [tab, setTab] = useState('chat');
  const [repos, setRepos] = useState([]);
  const [selectedRepo, setSelectedRepo] = useState('');
  const [messages, setMessages] = useState([{id:'welcome',role:'assistant',text:'Привет! Выбери репозиторий. Я могу читать PR, готовить Issues и поручать Qwen Code изменения в коде.'}]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [tasks, setTasks] = useState([]);
  const [error, setError] = useState('');
  const chatRef = useRef([]);

  useEffect(() => {
    (async () => {
      const savedUrl = await SecureStore.getItemAsync('server_url');
      const savedToken = await SecureStore.getItemAsync('app_token');
      if (savedUrl && savedToken) {
        setUrl(savedUrl); setToken(savedToken); setSettings(false);
      }
    })().catch(() => setError('Не удалось прочитать настройки'));
  }, []);

  const api = useCallback(async (route, method='GET', data) => {
    const base = url.trim().replace(/\/$/, '');
    if (!base.startsWith('https://') && !base.startsWith('http://localhost'))
      throw new Error('Нужен HTTPS-адрес сервера');
    const response = await fetch(`${base}${route}`, {
      method, headers: {Authorization:`Bearer ${token}`, 'Content-Type':'application/json'},
      ...(data === undefined ? {} : {body:JSON.stringify(data)}),
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
    return result;
  }, [url,token]);

  const refresh = useCallback(async () => {
    if (!url || !token || settings) return;
    try {
      const [r, t] = await Promise.all([api('/repos'), api('/tasks')]);
      setRepos(r.repos || []); setSelectedRepo(prev => prev || r.repos?.[0] || '');
      setTasks(t.tasks || []); setError('');
    } catch(e) { setError(String(e.message || e)); }
  }, [api,url,token,settings]);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    if (settings || !selectedRepo || !token) return;
    let subscription;
    (async () => {
      const permission = await Notifications.requestPermissionsAsync();
      if (permission.status !== 'granted') return;
      // Android native FCM token, NOT an Expo push-service token.
      const push = await Notifications.getDevicePushTokenAsync();
      if (typeof push.data === 'string')
        await api('/devices','POST',{token:push.data,repos:[selectedRepo]});
    })().catch(e => console.log('Push registration not configured:',String(e)));
    subscription = Notifications.addPushTokenListener(async push => {
      if (typeof push.data === 'string') {
        try { await api('/devices','POST',{token:push.data,repos:[selectedRepo]}); } catch(e) { console.log(e); }
      }
    });
    return () => subscription?.remove();
  }, [api,selectedRepo,settings,token]);

  const save = async () => {
    if (!url.trim().startsWith('https://') || token.trim().length < 20) {
      Alert.alert('Проверь настройки','Нужен HTTPS URL и длинный ключ приложения'); return;
    }
    await SecureStore.setItemAsync('server_url',url.trim().replace(/\/$/,''));
    await SecureStore.setItemAsync('app_token',token.trim());
    setSettings(false);
  };

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput(''); setLoading(true);
    setMessages(prev => [...prev,{id:`u-${Date.now()}`,role:'user',text}]);
    const prefix = selectedRepo ? `Текущий репозиторий: ${selectedRepo}. ` : '';
    try {
      const result = await api('/chat','POST',{message:prefix+text,history:chatRef.current.slice(-12)});
      chatRef.current = [...chatRef.current,{role:'user',content:prefix+text},{role:'assistant',content:result.reply}].slice(-12);
      setMessages(prev => [...prev,{id:`a-${Date.now()}`,role:'assistant',text:result.reply,actions:result.actions || []}]);
      refresh();
    } catch(e) { setMessages(prev => [...prev,{id:`e-${Date.now()}`,role:'error',text:String(e.message || e)}]); }
    finally { setLoading(false); }
  };

  const confirm = (id) => {
    Alert.alert('Подтвердить действие?', 'Запуск может изменить репозиторий или опубликовать комментарий в GitHub.', [
      {text:'Отмена',style:'cancel'},
      {text:'Подтвердить',onPress: async () => {
        try { await api(`/tasks/${id}/confirm`,'POST'); refresh(); Alert.alert('Поставлено в очередь','Результат появится в разделе «Задачи».'); }
        catch(e) { Alert.alert('Ошибка',String(e.message || e)); }
      }},
    ]);
  };

  const renderMessage = ({item}) => <View style={[s.bubble, item.role === 'user' ? s.userBubble : s.aiBubble]}>
    <Text style={s.message}>{item.text}</Text>
    {(item.actions || []).map((a,i) => <View key={i} style={s.action}>
      {a.type === 'confirmation_required' ? <>
        <Text style={s.label}>ПОДТВЕРЖДЕНИЕ · {a.kind} · {a.repo}</Text>
        <Text style={s.small}>{JSON.stringify(a.details,null,2)}</Text>
        <Btn label="Подтвердить действие" onPress={() => confirm(a.task_id)} />
      </> : <Text style={s.small}>{JSON.stringify(a.result || a.message,null,2)}</Text>}
    </View>)}
  </View>;

  if (settings) return <SafeAreaView style={s.safe}><ScrollView contentContainerStyle={s.settings}>
    <Text style={s.heading}>Qwen GitHub Agent</Text>
    <Text style={s.muted}>Подключение к твоему серверу. GitHub и Qwen API ключи остаются на бэкенде.</Text>
    <Text style={s.label}>HTTPS АДРЕС БЭКЕНДА</Text>
    <TextInput style={s.input} value={url} onChangeText={setUrl} placeholder="https://your-backend.onrender.com" placeholderTextColor={COLORS.muted} autoCapitalize="none" />
    <Text style={s.label}>КЛЮЧ ДОСТУПА К ПРИЛОЖЕНИЮ</Text>
    <TextInput style={s.input} value={token} onChangeText={setToken} secureTextEntry placeholder="APP_API_TOKEN" placeholderTextColor={COLORS.muted} autoCapitalize="none" />
    <Btn label="Сохранить и подключиться" onPress={() => save().catch(e => Alert.alert('Ошибка',String(e)))} />
  </ScrollView></SafeAreaView>;

  return <SafeAreaView style={s.safe}>
    <View style={s.header}>
      <View><Text style={s.heading}>Qwen <Text style={{color:COLORS.purple}}>GitHub</Text></Text>
        <Text style={s.muted}>AI-разработка с телефона</Text></View>
      <Btn label="⚙" secondary onPress={() => setSettings(true)} />
    </View>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.repoBar} contentContainerStyle={{padding:9,gap:8}}>
      {repos.map(r => <TouchableOpacity key={r} style={[s.repoPill,selectedRepo===r && s.activePill]} onPress={() => setSelectedRepo(r)}>
        <Text style={s.repoText}>{r}</Text>
      </TouchableOpacity>)}
    </ScrollView>
    {!!error && <Text style={s.error}>{error}</Text>}
    <View style={s.tabs}>
      <Btn label="Чат" secondary={tab !== 'chat'} onPress={() => setTab('chat')} />
      <Btn label={`Задачи (${tasks.length})`} secondary={tab !== 'tasks'} onPress={() => setTab('tasks')} />
      <Btn label="Обновить" secondary onPress={refresh} />
    </View>
    {tab === 'chat' ? <>
      <FlatList data={messages} renderItem={renderMessage} keyExtractor={m => m.id}
        style={{flex:1}} contentContainerStyle={{padding:14,paddingBottom:22}} />
      <View style={s.quick}>
        {['Покажи PR', 'Проверь последний PR', 'Проиндексируй репозиторий'].map(t => <TouchableOpacity key={t} style={s.repoPill} onPress={() => setInput(t)}>
          <Text style={s.small}>{t}</Text></TouchableOpacity>)}
      </View>
      <View style={s.composer}>
        <TextInput style={[s.input,{flex:1,maxHeight:130}]} value={input} onChangeText={setInput} placeholder="Напиши задачу..." placeholderTextColor={COLORS.muted} multiline />
        {loading ? <ActivityIndicator color={COLORS.purple} /> : <Btn label="➤" onPress={send} />}
      </View>
    </> : <FlatList style={{flex:1}} data={tasks} keyExtractor={item => item.id} contentContainerStyle={{padding:14}} renderItem={({item}) => <View style={s.task}>
      <Text style={s.label}>{item.kind.toUpperCase()} · {item.repo}</Text>
      <Text style={s.message}>{item.status}</Text>
      <Text style={s.small}>{item.result || JSON.stringify(JSON.parse(item.args))}</Text>
      {item.status === 'pending_confirmation' && <Btn label="Подтвердить" onPress={() => confirm(item.id)} />}
    </View>} />}
  </SafeAreaView>;
}

const s = StyleSheet.create({
  safe:{flex:1,backgroundColor:COLORS.bg},
  header:{padding:16,flexDirection:'row',justifyContent:'space-between',alignItems:'center'},
  heading:{fontSize:25,fontWeight:'800',color:COLORS.ink},
  muted:{fontSize:12,color:COLORS.muted,marginTop:3},
  settings:{padding:22,gap:14,justifyContent:'center',flexGrow:1},
  label:{color:COLORS.purple,fontSize:11,fontWeight:'800',letterSpacing:.5,marginBottom:6},
  input:{backgroundColor:COLORS.panel,borderColor:COLORS.border,borderWidth:1,color:COLORS.ink,padding:12,borderRadius:13,minHeight:46},
  btn:{backgroundColor:COLORS.purple,paddingHorizontal:16,paddingVertical:11,borderRadius:12,alignItems:'center'},
  secondary:{backgroundColor:COLORS.panel,borderColor:COLORS.border,borderWidth:1},
  danger:{backgroundColor:COLORS.danger},disabled:{opacity:.5},
  btnText:{color:'white',fontWeight:'700'},
  repoBar:{maxHeight:60,flexGrow:0,borderTopWidth:1,borderBottomWidth:1,borderColor:COLORS.border},
  repoPill:{borderRadius:30,backgroundColor:COLORS.panel,padding:10,borderColor:COLORS.border,borderWidth:1},
  activePill:{backgroundColor:'#493474',borderColor:COLORS.purple},
  repoText:{color:COLORS.ink,fontSize:12},
  tabs:{flexDirection:'row',gap:8,padding:10},
  bubble:{maxWidth:'94%',padding:14,borderRadius:16,marginVertical:6},
  userBubble:{backgroundColor:'#44306e',alignSelf:'flex-end'},
  aiBubble:{backgroundColor:COLORS.panel,alignSelf:'flex-start',borderWidth:1,borderColor:COLORS.border},
  message:{color:COLORS.ink,fontSize:14,lineHeight:21},
  small:{color:COLORS.muted,fontSize:12,lineHeight:18},
  action:{marginTop:12,padding:8,borderTopWidth:1,borderColor:COLORS.border,gap:8},
  quick:{flexDirection:'row',gap:7,paddingHorizontal:8,paddingVertical:8,flexWrap:'wrap'},
  composer:{flexDirection:'row',padding:10,gap:10,alignItems:'flex-end',borderTopWidth:1,borderColor:COLORS.border},
  task:{backgroundColor:COLORS.panel,borderWidth:1,borderColor:COLORS.border,borderRadius:15,padding:14,gap:7,marginVertical:6},
  error:{color:COLORS.danger,paddingHorizontal:12},
});
