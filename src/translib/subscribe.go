///////////////////////////////////////////////////
//
// Copyright 2019 Broadcom Inc.
//
///////////////////////////////////////////////////

/*
Package translib defines the functions to be used by the subscribe 

handler to subscribe for a key space notification. It also has

functions to handle the key space notification from redis and

call the appropriate app module to handle them.

*/

package translib

import (
	"sync"
	"time"
	"bytes"
	"translib/db"
	log "github.com/golang/glog"
	"github.com/Workiva/go-datastructures/queue"
)

//Subscribe mutex for all the subscribe operations on the maps to be thread safe
var sMutex = &sync.Mutex{}

type notificationInfo struct{
	table               db.TableSpec
	key					db.Key
	dbno				db.DBNum
	needCache			bool
	path				string
	app				   *appInterface
	appInfo			   *appInfo
	cache			  []byte
	sKey			   *db.SKey
	dbs [db.MaxDB]	   *db.DB //used to perform get operations
	sDB				   *db.DB //Subscription DB should be used only for keyspace notification
}

type subscribeInfo struct{
	syncDone			bool
	q				   *queue.PriorityQueue
	nInfoArr		 []*notificationInfo
	stop				chan struct{}
	sDBs			 []*db.DB //Subscription DB should be used only for keyspace notification unsubscription
}

var nMap map[*db.SKey]*notificationInfo
var sMap map[*notificationInfo]*subscribeInfo
var stopMap map[chan struct{}]*subscribeInfo

func init() {
	nMap = make(map[*db.SKey]*notificationInfo)
	sMap = make(map[*notificationInfo]*subscribeInfo)
	stopMap	= make(map[chan struct{}]*subscribeInfo)
}

func runSubscribe(q *queue.PriorityQueue) error {
	var err error

	for i := 0; i < 10; i++ {
		time.Sleep(2 * time.Second)
		q.Put(&SubscribeResponse{
				Path:"/testPath",
				Payload:[]byte("test payload"),
				Timestamp:    time.Now().UnixNano(),
		})

	}

	return err
}

func startDBSubscribe(opt db.Options, nInfoList []*notificationInfo, sInfo *subscribeInfo) error {
	var sKeyList []*db.SKey

	for _, nInfo := range nInfoList {
		sKey := &db.SKey{ Ts: &nInfo.table, Key: &nInfo.key}
		sKeyList = append(sKeyList, sKey)
		nInfo.sKey = sKey
		nMap[sKey] = nInfo
		sMap[nInfo] = sInfo
	}

	sDB, err := db.SubscribeDB(opt, sKeyList, notificationHandler)

	if err == nil {
		sInfo.sDBs = append(sInfo.sDBs, sDB)
	} else {
		for i, nInfo := range nInfoList {
			delete(nMap, sKeyList[i])
			delete(sMap, nInfo)
		}
	}

	return err
}

func notificationHandler(d *db.DB, sKey *db.SKey, key *db.Key, event db.SEvent) error {
    log.Info("notificationHandler: d: ", d, " sKey: ", *sKey, " key: ", *key,
        " event: ", event)
	switch event {
	case db.SEventHSet:
	case db.SEventHDel:
	case db.SEventDel:
		sMutex.Lock()
		defer sMutex.Unlock()

		if sKey != nil {
			nInfo := nMap[sKey]
			sInfo := sMap[nInfo]

			isChanged := isCacheChanged(nInfo)

			if isChanged {
				sendNotification(sInfo, nInfo)
			}
		}
	}

    return nil
}

func updateCache(nInfo *notificationInfo) error {
	var err error

	json, err1 := getJson (nInfo)

	if err1 == nil {
		nInfo.cache = json
	} else {
		log.Error("Failed to get the Json for the path = ", nInfo.path)
		log.Error("Error returned = ", err1)

		nInfo.cache = []byte("{}")
	}

	return err
}

func isCacheChanged(nInfo *notificationInfo) bool {
	json, err := getJson (nInfo)

    if err == nil {
        if bytes.Equal(nInfo.cache, json) {
			log.Info("Cache is same as DB")
			return false
		} else {
			log.Info("Cache is NOT same as DB")
			nInfo.cache = json
			return true
		}
    }
	return false
}

func startSubscribe(sInfo *subscribeInfo, dbNotificationMap map[db.DBNum][]*notificationInfo) error {
	var err error

    sMutex.Lock()
	defer sMutex.Unlock()


    for dbno, nInfoArr := range dbNotificationMap {
        opt := getDBOptions(dbno)
        err = startDBSubscribe(opt, nInfoArr, sInfo)

		if err != nil {
			//TODO:Need to cleanup old subscriptions
			return err
		}

        sInfo.nInfoArr = append(sInfo.nInfoArr, nInfoArr...)
    }

	stopMap[sInfo.stop] = sInfo

    for i, nInfo := range sInfo.nInfoArr {
        err = updateCache(nInfo)

		if err != nil {
			//TODO:Need to cleanup all subscriptions
            return err
        }

		if i == len(sInfo.nInfoArr)-1 {
			sInfo.syncDone = true
		}

		sendNotification(sInfo, nInfo)
    }
	printAllMaps()

	go stophandler(sInfo.stop)

	return err
}

func getJson (nInfo *notificationInfo) ([]byte, error) {
    var payload []byte

	app := nInfo.app
	path := nInfo.path
	appInfo := nInfo.appInfo

    err := appInitialize(app, appInfo, path, nil, GET)

    if  err != nil {
        return payload, err
    }

	dbs := nInfo.dbs

    err = (*app).translateGet (dbs)

    if err != nil {
        return payload, err
    }

    resp, err := (*app).processGet(dbs)

    if err == nil {
        payload = resp.Payload
    }

    return payload, err
}

func sendNotification(sInfo *subscribeInfo, nInfo *notificationInfo){
	log.Info("Sending notification for sInfo = ", sInfo)
	log.Info("payload = ", string(nInfo.cache))
	sInfo.q.Put(&SubscribeResponse{
			Path:nInfo.path,
			Payload:nInfo.cache,
			Timestamp:    time.Now().UnixNano(),
			SyncComplete: sInfo.syncDone,
	})
}

func stophandler(stop chan struct{}) {
	for {
		select {
		case <-stop:
			log.Info("stop channel signalled")
		    sMutex.Lock()
			defer sMutex.Unlock()

			sInfo := stopMap[stop]

			for _, sDB := range sInfo.sDBs {
				sDB.UnsubscribeDB()
			}

			for _, nInfo := range sInfo.nInfoArr {
				delete(nMap, nInfo.sKey)
				delete(sMap, nInfo)
			}

			delete(stopMap, stop)
			printAllMaps()

			return
		}
	}

	return
}

func printnMap() {
	log.Info("Printing the contents of nMap")
	for sKey, nInfo := range nMap {
		log.Info("sKey = ", sKey)
		log.Info("nInfo = ", nInfo)
	}
}

func printStopMap() {
	log.Info("Printing the contents of stopMap")
	for stop, sInfo := range stopMap {
		log.Info("stop = ", stop)
		log.Info("sInfo = ", sInfo)
	}
}

func printsMap() {
	log.Info("Printing the contents of sMap")
	for sInfo, nInfo := range sMap {
		log.Info("nInfo = ", nInfo)
		log.Info("sKey = ", sInfo)
	}
}

func printAllMaps() {
	printnMap()
	printsMap()
	printStopMap()
}
