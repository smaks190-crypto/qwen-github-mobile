import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, Linking, Modal, ScrollView, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { makePullRequestUrl } from '../utils/pullRequest';

const C = { bg:'#0d0d14', panel:'#1a1928', border:'#313047', ink:'#f5f1ff', muted:'#a8a4bf', purple:'#9569ff', green:'#61d6a1' };

function Field({ label, value, onChangeText, placeholder, multiline }) {
  return <View style={s.field}>
    <Text style={s.label}>{label}</Text>
    <TextInput style={[s.input, multiline && s.multiline]} value={value}
      onChangeText={onChangeText} placeholder={placeholder} placeholderTextColor={C.muted}
      autoCapitalize="none" autoCorrect={false} multiline={multiline}/>
  </View>;
}

/**
 * The panel prepares a PR; GitHub performs final creation after the user presses
 * its own Create pull request / Create draft pull request button.
 */
export default function CreatePRModal({ visible, prepared, selectedRepo, onClose }) {
  const [repo, setRepo] = useState('');
  const [head, setHead] = useState('');
  const [base, setBase] = useState('main');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [opening, setOpening] = useState(false);

  useEffect(() => {
    if (!visible) return;
    setRepo(prepared?.repo || selectedRepo || '');
    setHead(prepared?.head || '');
    setBase(prepared?.base || 'main');
    setTitle(prepared?.title || '');
    setBody(prepared?.body || '');
  }, [visible, prepared, selectedRepo]);

  const openGitHub = async () => {
    if (opening) return;
    try {
      const url = makePullRequestUrl({repo, head, base, title, body});
      setOpening(true);
      await Linking.openURL(url);
      onClose();
    } catch (err) {
      Alert.alert('Не удалось открыть создание PR', String(err?.message || err));
    } finally {
      setOpening(false);
    }
  };

  return <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
    <View style={s.shade}>
      <View style={s.sheet}>
        <View style={s.header}>
          <View style={{flex:1}}>
            <Text style={s.heading}>Создать PR</Text>
            <Text style={s.subtitle}>Проверь изменения перед публикацией</Text>
          </View>
          <TouchableOpacity accessibilityLabel="Закрыть" style={s.close} onPress={onClose}>
            <Text style={s.text}>✕</Text>
          </TouchableOpacity>
        </View>
        <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={s.fields}>
          <Field label="РЕПОЗИТОРИЙ" value={repo} onChangeText={setRepo} placeholder="owner/repo" />
          <Field label="ВЕТКА С ИЗМЕНЕНИЯМИ (head)" value={head} onChangeText={setHead} placeholder="qwen/task-..." />
          <Field label="ЦЕЛЕВАЯ ВЕТКА (base)" value={base} onChangeText={setBase} placeholder="main" />
          <Field label="НАЗВАНИЕ PR" value={title} onChangeText={setTitle} placeholder="Что изменено?" />
          <Field label="ОПИСАНИЕ" value={body} onChangeText={setBody} placeholder="Что сделано и как проверить?" multiline />
          <View style={s.notice}>
            <Text style={s.noticeText}>PR ещё не создан. GitHub откроет форму с заполненными полями. Там можно проверить diff, выбрать Draft PR и окончательно подтвердить создание. Ветка должна быть отправлена в GitHub.</Text>
          </View>
        </ScrollView>
        <View style={s.footer}>
          <TouchableOpacity style={[s.button,s.cancel]} onPress={onClose}><Text style={s.text}>Отмена</Text></TouchableOpacity>
          <TouchableOpacity style={[s.button,s.create]} disabled={opening} onPress={openGitHub}>
            {opening ? <ActivityIndicator color="white"/> : <Text style={s.text}>Продолжить в GitHub ↗</Text>}
          </TouchableOpacity>
        </View>
      </View>
    </View>
  </Modal>;
}

const s = StyleSheet.create({
  shade:{flex:1,justifyContent:'flex-end',backgroundColor:'#000a'},
  sheet:{height:'89%',backgroundColor:C.bg,borderTopLeftRadius:24,borderTopRightRadius:24,borderWidth:1,borderColor:C.border,paddingTop:16},
  header:{paddingHorizontal:18,paddingBottom:14,flexDirection:'row',alignItems:'center'},
  heading:{fontSize:24,fontWeight:'800',color:C.ink},
  subtitle:{color:C.muted,marginTop:4,fontSize:12},
  close:{padding:12,borderRadius:12,backgroundColor:C.panel},
  text:{color:C.ink,fontWeight:'700'},
  fields:{paddingHorizontal:18,paddingBottom:20,gap:14},
  field:{gap:7},
  label:{color:C.purple,fontSize:11,fontWeight:'800'},
  input:{backgroundColor:C.panel,borderRadius:12,borderWidth:1,borderColor:C.border,padding:12,minHeight:46,color:C.ink},
  multiline:{minHeight:120,textAlignVertical:'top'},
  notice:{padding:13,borderRadius:12,borderWidth:1,borderColor:C.border,backgroundColor:C.panel},
  noticeText:{color:C.muted,lineHeight:19,fontSize:12},
  footer:{padding:16,flexDirection:'row',gap:10,borderTopWidth:1,borderColor:C.border},
  button:{padding:14,borderRadius:12,alignItems:'center',justifyContent:'center'},
  cancel:{flex:1,backgroundColor:C.panel},
  create:{flex:2,backgroundColor:C.purple}
});
