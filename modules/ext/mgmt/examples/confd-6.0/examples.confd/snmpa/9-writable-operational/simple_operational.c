/*
 * Copyright 2005-2011 Tail-F Systems AB
 */


#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/poll.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>

#include <confd_lib.h>
#include <confd_dp.h>
#include "SIMPLE-MIB.h"

/* this code is an external database, the data model */
/* that we handle reside in SIMPLE-MIB.yang */

/* Our daemon context as a global variable */
/* as well as the ConfD callback function structs */

static struct confd_daemon_ctx *dctx;
static struct confd_trans_cbs trans;
static struct confd_data_cbs  data;
static int ctlsock;
static int workersock;



/* transaction callbacks */

static int t_init(struct confd_trans_ctx *tctx)
{
    confd_trans_set_fd(tctx, workersock);
    return CONFD_OK;
}

/* In our set_elem callback, we return CONFD_ACCUMULATE.  Then
   at commit time, we perform the actual request. */
static int t_commit(struct confd_trans_ctx *tctx)
{
    struct confd_tr_item *item = tctx->accumulated;
    while (item) {
        confd_hkeypath_t *keypath = item->hkp;
        confd_value_t *leaf = &(keypath->v[0][0]);
        switch(item->op) {
        case C_SET_ELEM:
            switch (CONFD_GET_XMLTAG(leaf)) {
            case SIMPLE_MIB_rebootRouter:
                if (CONFD_GET_INT32(item->val) == 1) {
                    printf("** REBOOT REQUESTED **\n");
                } else {
                    /* other values are ignored */
                }
                break;
            }
            break;
        default:
            break;
        }
        item = item->next;
    }
    return CONFD_OK;
}

/* data callbacks that manipulate the db */

/* keypath tells us the path choosen down the XML tree */
/* We need to return a list of all server keys here */

static int get_next(struct confd_trans_ctx *tctx,
                    confd_hkeypath_t *keypath,
                    long next)
{
    confd_data_reply_next_key(tctx, NULL, -1, -1);
    return CONFD_OK;
}



static int get_elem(struct confd_trans_ctx *tctx,
                    confd_hkeypath_t *keypath)
{
    confd_value_t v;

    /* switch on xml elem tag */
    switch (CONFD_GET_XMLTAG(&(keypath->v[0][0]))) {
    case SIMPLE_MIB_rebootRouter:
        CONFD_SET_INT32(&v, 0);
        break;
    default:
        confd_trans_seterr(tctx, "xml tag not handled");
        return CONFD_ERR;
    }
    confd_data_reply_value(tctx, &v);
    return CONFD_OK;
}


static int set_elem(struct confd_trans_ctx *tctx,
                    confd_hkeypath_t *keypath,
                    confd_value_t *newval)
{
    switch (CONFD_GET_XMLTAG(&(keypath->v[0][0]))) {
    case SIMPLE_MIB_rebootRouter:
        if (CONFD_GET_INT32(newval) == 0) {
            /* setting to 0 results in inconsistentValue */
            confd_trans_seterr_extended(tctx, CONFD_ERRCODE_INCONSISTENT_VALUE,
                                        0, 0, "");
            return CONFD_ERR;
        }
    }

    return CONFD_ACCUMULATE;
}

int main(int argc, char *argv[]) {
    struct sockaddr_in addr;
    int debuglevel = CONFD_TRACE;

    int c;

    while ((c = getopt(argc, argv, "qdtp")) != -1) {
        switch (c) {
        case 'q':
            debuglevel = CONFD_SILENT;
            break;
        case 'd':
            debuglevel = CONFD_DEBUG;
            break;
        case 't':
            debuglevel = CONFD_TRACE;
            break;
        case 'p':
            debuglevel = CONFD_PROTO_TRACE;
            break;
        default:
            fprintf(stderr, "usage: simple [-qdtp]\n");
            exit(1);
        }
    }

    /* Transaction callbacks */
    trans.init = t_init;
    trans.write_start = NULL;
    trans.commit = t_commit;

    /* And finallly these are our read/write callbacks for  */
    /* the operational leafs */
    data.get_elem = get_elem;
    data.get_next = get_next;
    data.set_elem = set_elem;
    data.create   = NULL;
    data.remove   = NULL;
    strcpy(data.callpoint, SIMPLE_MIB__callpointid_simplecp);

    /* Init library  */
    confd_init("simple_operational", stderr, debuglevel);

    /* Initialize daemon context */
    if ((dctx = confd_init_daemon("simple_operational"))
        == NULL)
        confd_fatal("Failed to initialize confd\n");

    if ((ctlsock = socket(PF_INET, SOCK_STREAM, 0)) < 0 )
        confd_fatal("Failed to open ctlsocket\n");

    addr.sin_addr.s_addr = inet_addr("127.0.0.1");
    addr.sin_family = AF_INET;
    addr.sin_port = htons(CONFD_PORT);

    if (confd_load_schemas((struct sockaddr*)&addr,
                           sizeof (struct sockaddr_in)) != CONFD_OK)
        confd_fatal("Failed to load schemas from confd\n");

    /* Create the first control socket, all requests to */
    /* create new transactions arrive here */

    if (confd_connect(dctx, ctlsock, CONTROL_SOCKET, (struct sockaddr*)&addr,
                      sizeof (struct sockaddr_in)) != CONFD_OK)
        confd_fatal("Failed to confd_connect() to confd \n");


    /* Also establish a workersocket, this is the most simple */
    /* case where we have just one ctlsock and one workersock */

    if ((workersock = socket(PF_INET, SOCK_STREAM, 0)) < 0 )
        confd_fatal("Failed to open workersocket\n");
    if (confd_connect(dctx, workersock, WORKER_SOCKET,(struct sockaddr*)&addr,
                      sizeof (struct sockaddr_in)) < 0)
        confd_fatal("Failed to confd_connect() to confd \n");


    confd_register_trans_cb(dctx, &trans);

    /* we also need to register our read/write callbacks */

    if (confd_register_data_cb(dctx, &data) == CONFD_ERR)
        confd_fatal("Failed to register data cb \n");

    if (confd_register_done(dctx) != CONFD_OK)
        confd_fatal("Failed to complete registration \n");

    printf("Registered with ConfD\n");

    while (1) {
        struct pollfd set[2];
        int ret;

        set[0].fd = ctlsock;
        set[0].events = POLLIN;
        set[0].revents = 0;

        set[1].fd = workersock;
        set[1].events = POLLIN;
        set[1].revents = 0;


        if (poll(set, sizeof(set)/sizeof(*set), -1) < 0) {
            perror("Poll failed:");
            continue;
        }

        /* Check for I/O */
        if (set[0].revents & POLLIN) {
            if ((ret = confd_fd_ready(dctx, ctlsock)) == CONFD_EOF) {
                confd_fatal("Control socket closed\n");
            } else if (ret == CONFD_ERR && confd_errno != CONFD_ERR_EXTERNAL) {
                confd_fatal("Error on control socket request: %s (%d): %s\n",
                     confd_strerror(confd_errno), confd_errno, confd_lasterr());
            }
        }
        if (set[1].revents & POLLIN) {
            if ((ret = confd_fd_ready(dctx, workersock)) == CONFD_EOF) {
                confd_fatal("Worker socket closed\n");
            } else if (ret == CONFD_ERR && confd_errno != CONFD_ERR_EXTERNAL) {
                confd_fatal("Error on worker socket request: %s (%d): %s\n",
                     confd_strerror(confd_errno), confd_errno, confd_lasterr());
            }
        }

    }
}

