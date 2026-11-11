import unittest
from nora.classroom import Events, observations

ZONES = [{'name':'Mesa 1','bbox':[0,0,500,1000]}]

class ClassroomTests(unittest.TestCase):
    def test_phone_must_be_with_a_person(self):
        phone = {'name':'smartphone','bbox':[100,100,150,150]}
        self.assertFalse(observations([phone],ZONES)['Mesa 1']['phone'])
        person = {'name':'man','bbox':[50,50,400,900]}
        self.assertTrue(observations([person,phone],ZONES)['Mesa 1']['phone'])

    def test_debounce_initial_empty_and_departure_return(self):
        events=[]
        track=Events(ZONES,lambda *args: events.append(args))
        def sample(at,occupied):
            track.update({'Mesa 1':{'occupied':occupied,'phone':False}},at)
        sample(0,False);sample(4,False)
        self.assertEqual(events,[])
        sample(5,True);sample(9,True)
        events.clear()
        sample(10,False);sample(11,True)
        self.assertEqual(events,[])
        sample(12,False);sample(16,False)
        sample(17,True);sample(21,True)
        self.assertEqual([e[1] for e in events],['saida_aparente','retorno_aparente'])

    def test_gap_does_not_create_a_departure(self):
        events=[]
        track=Events(ZONES,lambda *args:events.append(args))
        for at in [0,4]:
            track.update({'Mesa 1':{'occupied':True,'phone':False}},at)
        events.clear()
        for at in [20,24]:
            track.update({'Mesa 1':{'occupied':False,'phone':False}},at)
        self.assertEqual([e[1] for e in events],['intervalo_sem_observacao'])
